from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.jobs_service import JobsService

router = APIRouter(prefix='/jobs', tags=['jobs'])


@router.get('/')
def list_jobs(db: Session = Depends(get_db)):
    svc = JobsService(db)
    return svc.list_jobs()
