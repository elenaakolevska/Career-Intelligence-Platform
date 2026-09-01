from fastapi import APIRouter, Depends, HTTPException, WebSocket
from sqlalchemy.orm import Session

from app import models
from app.api.deps import get_current_user, get_db, require_cv_owner
from app.interview.ws_handler import handle_interview_websocket
from app.schemas.interview import (
    InterviewAnswerCreate,
    InterviewComplete,
    InterviewCreate,
    InterviewHistoryRead,
    InterviewRead,
    InterviewStateRead,
    InterviewSummary,
)
from app.services.interview_service import InterviewService

router = APIRouter(prefix='/interview', tags=['interview'])


def _require_session_owner(
    session_id: int,
    user: models.User,
    db: Session,
) -> models.InterviewSession:
    svc = InterviewService(db)
    session = svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail='Interview session not found')
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail='Not allowed to access this interview')
    return session


@router.post('/start', response_model=InterviewRead)
def start_interview(
    payload: InterviewCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a new interview session (persisted, resumable — P7-01)."""
    if payload.user_id is not None and payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail='user_id does not match authenticated user')
    if payload.cv_id is not None:
        require_cv_owner(payload.cv_id, current_user, db)
    return InterviewService(db).start_session(
        current_user.id,
        role=payload.role,
        cv_id=payload.cv_id,
        difficulty=payload.difficulty or 'junior',
    )


@router.get('/me', response_model=list[InterviewRead])
def list_my_interviews(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return InterviewService(db).list_sessions_for_user(current_user.id)


@router.get('/me/summary', response_model=list[InterviewSummary])
def list_my_interview_summaries(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return InterviewService(db).list_session_summaries(current_user.id)


@router.get('/user/{user_id}', response_model=list[InterviewRead])
def list_user_interviews(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List a user's sessions newest-first (must be the authenticated user)."""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Not allowed to list another user\'s interviews')
    return InterviewService(db).list_sessions_for_user(user_id)


@router.get('/user/{user_id}/summary', response_model=list[InterviewSummary])
def list_user_interview_summaries(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Not allowed to list another user\'s interviews')
    return InterviewService(db).list_session_summaries(user_id)


@router.websocket('/ws/{session_id}')
async def interview_websocket(websocket: WebSocket, session_id: int):
    """Real-time interview chat: question / answer / feedback over WebSocket (P7-04)."""
    await handle_interview_websocket(websocket, session_id)


@router.get('/{session_id}', response_model=InterviewRead)
def get_interview(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _require_session_owner(session_id, current_user, db)
    return InterviewService(db)._to_read(session)


@router.get('/{session_id}/history', response_model=InterviewHistoryRead)
def get_interview_history(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_session_owner(session_id, current_user, db)
    history = InterviewService(db).get_history(session_id)
    if not history:
        raise HTTPException(status_code=404, detail='Interview session not found')
    return history


@router.post('/{session_id}/resume', response_model=InterviewRead)
def resume_interview(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_session_owner(session_id, current_user, db)
    result = InterviewService(db).resume_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail='Interview session not found')
    return result


@router.post('/{session_id}/question', response_model=InterviewRead)
def generate_interview_question(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _require_session_owner(session_id, current_user, db)
    if session.status in {'completed', 'abandoned'}:
        raise HTTPException(
            status_code=409,
            detail=f'Cannot generate questions for {session.status} session',
        )
    result = InterviewService(db).generate_next_question(session_id)
    if not result:
        raise HTTPException(status_code=404, detail='Interview session not found')
    return result


@router.post('/{session_id}/answer', response_model=InterviewRead)
def submit_interview_answer(
    session_id: int,
    payload: InterviewAnswerCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _require_session_owner(session_id, current_user, db)
    svc = InterviewService(db)
    if session.status in {'completed', 'abandoned'}:
        raise HTTPException(
            status_code=409,
            detail=f'Cannot submit answers for {session.status} session',
        )
    result = svc.submit_answer(session_id, payload.answer)
    if result is None:
        if not svc.get_session(session_id):
            raise HTTPException(status_code=404, detail='Interview session not found')
        raise HTTPException(
            status_code=409,
            detail='No pending question to answer — call POST /question first',
        )
    return result


@router.post('/{session_id}/complete', response_model=InterviewRead)
def complete_interview(
    session_id: int,
    payload: InterviewComplete | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_session_owner(session_id, current_user, db)
    svc = InterviewService(db)
    overall = payload.overall_feedback if payload else None
    result = svc.complete_session(session_id, overall_feedback=overall)
    if not result:
        raise HTTPException(status_code=404, detail='Interview session not found')
    return result


@router.post('/{session_id}/abandon', response_model=InterviewRead)
def abandon_interview(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_session_owner(session_id, current_user, db)
    result = InterviewService(db).abandon_session(session_id)
    if not result:
        raise HTTPException(status_code=404, detail='Interview session not found')
    return result


@router.get('/{session_id}/state', response_model=InterviewStateRead)
def get_interview_state(
    session_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_session_owner(session_id, current_user, db)
    payload = InterviewService(db).state_payload(session_id)
    if not payload:
        raise HTTPException(status_code=404, detail='Interview session not found')
    return payload
