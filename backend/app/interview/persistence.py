"""InterviewSession ORM ↔ InterviewGraphState mapping (P7-01)."""

from __future__ import annotations

import json
from typing import Any

from app import models
from app.interview.state import (
    InterviewGraphState,
    deserialize_interview_state,
    initial_interview_state,
    recompute_running_score,
    serialize_interview_state,
)


def _parse_history(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def interview_session_to_state(session: models.InterviewSession) -> InterviewGraphState:
    """Load resumable graph state from a persisted InterviewSession."""
    if session.state_json:
        try:
            state = deserialize_interview_state(session.state_json)
            # Keep DB identity authoritative
            state['session_id'] = session.id
            state['user_id'] = session.user_id
            return state
        except Exception:
            pass

    history = _parse_history(session.history_json)
    running, count = recompute_running_score(history)  # type: ignore[arg-type]
    if session.running_score is not None:
        running = float(session.running_score)
        count = count or len([t for t in history if t.get('score') is not None])

    status = session.status or ('active' if session.in_progress else 'completed')
    unanswered = None
    if history:
        last = history[-1]
        if last.get('question') and not last.get('answer'):
            unanswered = last.get('question')

    return {
        'session_id': session.id,
        'user_id': session.user_id,
        'cv_id': session.cv_id,
        'target_role': session.role,
        'difficulty': session.difficulty or 'junior',
        'status': status,  # type: ignore[typeddict-item]
        'history': history,  # type: ignore[typeddict-item]
        'current_question': unanswered,
        'running_score': running,
        'score_count': count,
        'latest_feedback': (history[-1].get('feedback') if history else None),
        'overall_feedback': session.overall_feedback,
        'errors': [],
        'warnings': [],
        'node_log': [],
    }


def apply_state_to_session(session: models.InterviewSession, state: InterviewGraphState) -> models.InterviewSession:
    """Write graph state fields onto an InterviewSession row (no commit)."""
    session.role = state.get('target_role') or session.role
    session.cv_id = state.get('cv_id') if state.get('cv_id') is not None else session.cv_id
    session.difficulty = state.get('difficulty') or session.difficulty
    status = state.get('status') or session.status or 'pending'
    session.status = status
    session.in_progress = status in {'pending', 'active'}
    history = list(state.get('history') or [])
    session.history_json = json.dumps(history, ensure_ascii=False, default=str)
    running = state.get('running_score')
    session.running_score = float(running) if running is not None else None
    session.overall_feedback = state.get('overall_feedback')
    # Persist full snapshot for faithful resume (WebSocket reconnect, P7-04/05)
    snap = dict(state)
    snap['session_id'] = session.id
    session.state_json = serialize_interview_state(snap)  # type: ignore[arg-type]
    return session


def new_session_state_from_create(
    *,
    user_id: int,
    target_role: str | None = None,
    cv_id: int | None = None,
    difficulty: str | None = 'junior',
) -> InterviewGraphState:
    return initial_interview_state(
        user_id=user_id,
        cv_id=cv_id,
        target_role=target_role,
        difficulty=difficulty,
    )
