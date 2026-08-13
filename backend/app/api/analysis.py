from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix='/analysis', tags=['analysis'])


@router.post('/run')
def run_analysis(cv_id: int, db: Session = Depends(get_db)):
    svc = AnalysisService(db)
    return svc.analyze(cv_id)
