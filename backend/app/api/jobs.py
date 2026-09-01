from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models
from app.api.deps import get_current_user, get_db, require_cv_owner
from app.schemas.job import JobRead
from app.services.jobs_service import JobsService

router = APIRouter(prefix='/jobs', tags=['jobs'])


@router.get('/', response_model=list[JobRead])
def list_jobs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    return JobsService(db).list_jobs()


@router.post('/seed-mock', response_model=list[JobRead])
def seed_mock_jobs(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _ = current_user
    jobs = JobsService(db).seed_mock_jobs()
    return [JobRead.model_validate(job) for job in jobs]


@router.post('/fetch/{cv_id}', response_model=list[JobRead])
def fetch_jobs_for_cv(
    cv_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_cv_owner(cv_id, current_user, db)
    jobs = JobsService(db).fetch_and_store_for_cv(cv_id)
    if not jobs:
        raise HTTPException(
            status_code=404,
            detail='No jobs returned from Adzuna for this profile (try a broader CV location or skills)',
        )
    return [JobRead.model_validate(job) for job in jobs]


@router.get('/match/{cv_id}')
def match_jobs_for_cv(
    cv_id: int,
    top_k: int = Query(default=10, ge=1, le=50),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_cv_owner(cv_id, current_user, db)
    return JobsService(db).match_for_cv(cv_id, top_k=top_k)
