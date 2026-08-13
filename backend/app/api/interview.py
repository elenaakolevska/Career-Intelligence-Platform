from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.interview_service import InterviewService

router = APIRouter(prefix='/interview', tags=['interview'])


@router.post('/start')
def start_interview(user_id: int, db: Session = Depends(get_db)):
    svc = InterviewService(db)
    return svc.start_session(user_id)
