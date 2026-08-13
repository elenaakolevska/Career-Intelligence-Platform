import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.exceptions import PDFExtractionError
from app.services.cv_service import CVService
from app.services.pdf_extractor import extract_pdf_text
from app.schemas.cv import CVRead, CVUploadResponse

router = APIRouter(prefix='/cv', tags=['cv'])

PDF_MAGIC = b'%PDF-'


@router.post('/upload', response_model=CVUploadResponse)
async def upload_cv(
    user_id: int = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)
):
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

    svc = CVService(db)
    existing = svc.get_cv_by_user_and_filename(user_id, unique_filename)
    if existing:
        return CVUploadResponse(id=existing.id, status=existing.status, duplicate=True)

    upload_path = Path(settings.cv_upload_dir) / unique_filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    upload_path.write_bytes(content)

    cv = svc.create_cv(user_id=user_id, filename=unique_filename, status='processing')

    try:
        raw_text = extract_pdf_text(upload_path)
        cv = svc.update_cv_text(cv.id, raw_text, status='completed')
    except PDFExtractionError:
        svc.update_cv_text(cv.id, '', status='failed')
        raise HTTPException(status_code=422, detail='PDF extraction failed: file may be encrypted, corrupted, or contain no extractable text')

    return CVUploadResponse(id=cv.id, status=cv.status)


@router.get('/{cv_id}', response_model=CVRead)
def get_cv(cv_id: int, db: Session = Depends(get_db)):
    svc = CVService(db)
    cv = svc.get_cv(cv_id)
    if not cv:
        raise HTTPException(status_code=404, detail='CV not found')
    return cv
