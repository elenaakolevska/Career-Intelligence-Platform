import hashlib
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.orm import Session

from app import models
from app.api.deps import get_current_user, get_db, require_cv_owner
from app.core.config import settings
from app.core.exceptions import PDFExtractionError, ValidationError
from app.schemas.cv import CVRead, CVUploadResponse
from app.services.ats_scorer import score_ats
from app.services.cv_parser import CVParserService
from app.services.cv_service import CVService
from app.services.pdf_extractor import extract_pdf_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/cv', tags=['cv'])

PDF_MAGIC = b'%PDF-'


def _serialize_cv(cv) -> CVRead:
    return CVRead(
        id=cv.id,
        user_id=cv.user_id,
        raw_text=cv.raw_text,
        summary=cv.summary,
        filename=cv.filename,
        status=cv.status,
        extraction_method=cv.extraction_method,
        error_message=cv.error_message,
        structured_data=CVService.structured_as_dict(cv),
        ats_score=cv.ats_score,
        ats_issues=CVService.ats_issues_as_list(cv),
    )


@router.get('/', response_model=list[CVRead])
def list_my_cvs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cvs = (
        db.query(models.CVProfile)
        .filter(models.CVProfile.user_id == current_user.id)
        .order_by(models.CVProfile.id.desc())
        .all()
    )
    return [_serialize_cv(cv) for cv in cvs]


@router.post('/upload', response_model=CVUploadResponse)
async def upload_cv(
    file: UploadFile = File(...),
    user_id: int | None = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Ignore spoofed form user_id — always use the JWT subject
    if user_id is not None and user_id != current_user.id:
        raise HTTPException(status_code=403, detail='user_id does not match authenticated user')

    if file.content_type != 'application/pdf':
        raise HTTPException(status_code=415, detail='Only PDF files are accepted')

    content = await file.read()

    if len(content) > settings.cv_max_upload_size_bytes:
        limit_mb = settings.cv_max_upload_size_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f'File exceeds maximum size of {limit_mb} MB',
        )

    if not content[:5] == PDF_MAGIC:
        raise HTTPException(status_code=415, detail='File is not a valid PDF')

    file_hash = hashlib.sha256(content).hexdigest()
    unique_filename = f'{file_hash}.pdf'
    owner_id = current_user.id

    svc = CVService(db)
    existing = svc.get_cv_by_user_and_filename(owner_id, unique_filename)
    if existing:
        return CVUploadResponse(
            id=existing.id,
            status=existing.status,
            duplicate=True,
            ats_score=existing.ats_score,
        )

    upload_path = Path(settings.cv_upload_dir) / unique_filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(content)

    cv = svc.create_cv(user_id=owner_id, filename=unique_filename, status='processing')

    try:
        raw_text, method = extract_pdf_text(upload_path)
        cv = svc.update_cv_text(cv.id, raw_text, status='processing', extraction_method=method)
    except PDFExtractionError as exc:
        svc.mark_failed(cv.id, str(exc.detail if hasattr(exc, 'detail') else exc))
        raise HTTPException(
            status_code=422,
            detail='PDF extraction failed: file may be encrypted, corrupted, or contain no extractable text',
        )

    structured = None
    if settings.enable_cv_llm_parse:
        try:
            structured = CVParserService().parse(raw_text)
        except ValidationError as exc:
            svc.mark_failed(cv.id, getattr(exc, 'detail', str(exc)))
            raise HTTPException(status_code=422, detail=f'CV parsing/validation failed: {exc.detail}')

    ats = None
    if settings.enable_ats_scoring:
        ats = score_ats(raw_text, structured, filename=unique_filename)

    if structured is not None:
        cv = svc.save_structured(cv.id, structured, ats=ats, status='completed')
    else:
        cv = svc.update_cv_text(cv.id, raw_text, status='completed', extraction_method=cv.extraction_method)
        if ats is not None:
            import json

            cv.ats_score = ats.score
            cv.ats_issues = json.dumps([i.model_dump() for i in ats.issues])
            db.add(cv)
            db.commit()
            db.refresh(cv)

    if settings.enable_auto_embed:
        try:
            from app.services.embedding_pipeline import embed_cv_profile

            embed_cv_profile(cv.id, db)
        except Exception:
            logger.exception('Auto-embed failed for cv_id=%s (non-fatal)', cv.id)

    return CVUploadResponse(id=cv.id, status=cv.status, ats_score=cv.ats_score)


@router.get('/{cv_id}', response_model=CVRead)
def get_cv(
    cv_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cv = require_cv_owner(cv_id, current_user, db)
    return _serialize_cv(cv)


@router.post('/{cv_id}/reparse', response_model=CVRead)
def reparse_cv(
    cv_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cv = require_cv_owner(cv_id, current_user, db)
    svc = CVService(db)
    if not cv.raw_text:
        raise HTTPException(status_code=422, detail='CV has no raw_text to parse')
    try:
        structured = CVParserService().parse(cv.raw_text)
        ats = score_ats(cv.raw_text, structured, filename=cv.filename) if settings.enable_ats_scoring else None
        cv = svc.save_structured(cv.id, structured, ats=ats, status='completed')
    except ValidationError as exc:
        svc.mark_failed(cv.id, getattr(exc, 'detail', str(exc)))
        raise HTTPException(status_code=422, detail=f'CV parsing/validation failed: {exc.detail}')
    return _serialize_cv(cv)
