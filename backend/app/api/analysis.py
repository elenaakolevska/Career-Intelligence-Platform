from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.api.deps import get_current_user, get_db, require_cv_owner
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix='/analysis', tags=['analysis'])


@router.post('/run/{cv_id}')
def run_analysis(
    cv_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the full multi-agent career graph for a CV (P6-08) and persist AnalysisResult."""
    require_cv_owner(cv_id, current_user, db)
    result = AnalysisService(db).analyze(cv_id)
    if result.get('error') == 'CV not found':
        raise HTTPException(status_code=404, detail='CV not found')
    return result


@router.get('/cv/{cv_id}/latest')
def get_latest_analysis(
    cv_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the most recent persisted AnalysisResult for a CV (P8-03)."""
    require_cv_owner(cv_id, current_user, db)
    payload = AnalysisService(db).get_latest(cv_id)
    if not payload:
        raise HTTPException(status_code=404, detail='No analysis found for this CV')
    return payload


@router.get('/{analysis_id}')
def get_analysis(
    analysis_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = AnalysisService(db).get_by_id(analysis_id)
    if not payload:
        raise HTTPException(status_code=404, detail='Analysis not found')
    cv_id = payload.get('cv_id')
    if cv_id is not None:
        require_cv_owner(int(cv_id), current_user, db)
    return payload
