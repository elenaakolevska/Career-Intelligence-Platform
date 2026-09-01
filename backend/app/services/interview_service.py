"""Interview session service — create, persist, resume, question, evaluate (P7-01…P7-03)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.clients.llm_client import LLMClient
from app.interview.evaluate_agent import run_evaluate_agent
from app.interview.persistence import (
    apply_state_to_session,
    interview_session_to_state,
    new_session_state_from_create,
)
from app.interview.question_agent import run_question_agent
from app.interview.state import InterviewGraphState, append_turn, find_pending_turn_index
from app.schemas.interview import InterviewRead, InterviewStateRead, InterviewTurnSchema


class InterviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def start_session(
        self,
        user_id: int,
        *,
        role: str | None = None,
        cv_id: int | None = None,
        difficulty: str | None = 'junior',
    ) -> InterviewRead:
        state = new_session_state_from_create(
            user_id=user_id,
            target_role=role,
            cv_id=cv_id,
            difficulty=difficulty,
        )
        session = models.InterviewSession(
            user_id=user_id,
            cv_id=cv_id,
            role=role,
            difficulty=difficulty or 'junior',
            status='pending',
            in_progress=True,
        )
        self.db.add(session)
        self.db.flush()  # assign id
        state['session_id'] = session.id
        state['status'] = 'active'
        apply_state_to_session(session, state)
        session.status = 'active'
        session.in_progress = True
        self.db.commit()
        self.db.refresh(session)
        return self._to_read(session)

    def get_session(self, session_id: int) -> models.InterviewSession | None:
        return (
            self.db.query(models.InterviewSession)
            .filter(models.InterviewSession.id == session_id)
            .first()
        )

    def load_state(self, session_id: int) -> InterviewGraphState | None:
        session = self.get_session(session_id)
        if not session:
            return None
        return interview_session_to_state(session)

    def resume_session(self, session_id: int) -> InterviewRead | None:
        """Return session for continuation; marks abandoned sessions as not resumable."""
        session = self.get_session(session_id)
        if not session:
            return None
        if session.status == 'abandoned':
            return self._to_read(session)
        # Re-hydrate snapshot so callers always get latest mapped state
        state = interview_session_to_state(session)
        if session.status == 'completed':
            return self._to_read(session, state=state)
        state['status'] = 'active'
        apply_state_to_session(session, state)
        session.status = 'active'
        session.in_progress = True
        self.db.commit()
        self.db.refresh(session)
        return self._to_read(session)

    def save_state(self, session_id: int, state: InterviewGraphState) -> InterviewRead | None:
        session = self.get_session(session_id)
        if not session:
            return None
        apply_state_to_session(session, state)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return self._to_read(session)

    def record_turn_for_resume_test(
        self,
        session_id: int,
        *,
        question: str,
        answer: str | None = None,
        score: float | None = None,
        feedback: str | None = None,
    ) -> InterviewRead | None:
        """Helper used by P7-01 tests / early wiring before P7-02/03 agents exist."""
        state = self.load_state(session_id)
        if state is None:
            return None
        state = append_turn(
            state,
            question=question,
            answer=answer,
            score=score,
            feedback=feedback,
        )
        return self.save_state(session_id, state)

    def generate_next_question(
        self,
        session_id: int,
        *,
        llm: LLMClient | None = None,
    ) -> InterviewRead | None:
        """Generate a role-specific technical question and persist it in history (P7-02)."""
        session = self.get_session(session_id)
        if not session:
            return None
        if session.status in {'completed', 'abandoned'}:
            return self._to_read(session)

        state = interview_session_to_state(session)
        # If the latest turn is still unanswered, return it rather than stacking questions
        history = list(state.get('history') or [])
        if history:
            last = history[-1]
            if last.get('question') and not last.get('answer'):
                return self._to_read(session, state=state)

        state = run_question_agent(state, db=self.db, llm=llm)
        return self.save_state(session_id, state)

    def submit_answer(
        self,
        session_id: int,
        answer: str,
        *,
        llm: LLMClient | None = None,
    ) -> InterviewRead | None:
        """Evaluate the pending answer and persist score + feedback (P7-03)."""
        session = self.get_session(session_id)
        if not session:
            return None
        if session.status in {'completed', 'abandoned'}:
            return self._to_read(session)

        state = interview_session_to_state(session)
        if find_pending_turn_index(state.get('history')) is None:
            return None  # caller maps to 409

        state = run_evaluate_agent(state, answer=answer, llm=llm)
        return self.save_state(session_id, state)

    def list_sessions_for_user(self, user_id: int) -> list[InterviewRead]:
        rows = (
            self.db.query(models.InterviewSession)
            .filter(models.InterviewSession.user_id == user_id)
            .order_by(
                models.InterviewSession.created_at.desc(),
                models.InterviewSession.id.desc(),
            )
            .all()
        )
        return [self._to_read(r) for r in rows]

    def list_session_summaries(self, user_id: int) -> list:
        from app.schemas.interview import InterviewSummary

        rows = (
            self.db.query(models.InterviewSession)
            .filter(models.InterviewSession.user_id == user_id)
            .order_by(
                models.InterviewSession.created_at.desc(),
                models.InterviewSession.id.desc(),
            )
            .all()
        )
        out: list[InterviewSummary] = []
        for row in rows:
            state = interview_session_to_state(row)
            out.append(
                InterviewSummary(
                    id=row.id,
                    user_id=row.user_id,
                    role=row.role,
                    difficulty=row.difficulty,
                    status=row.status or 'pending',
                    in_progress=bool(row.in_progress),
                    running_score=row.running_score,
                    turn_count=len(state.get('history') or []),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return out

    def get_history(self, session_id: int):
        from app.schemas.interview import InterviewHistoryRead

        session = self.get_session(session_id)
        if not session:
            return None
        read = self._to_read(session)
        return InterviewHistoryRead(
            session_id=read.id,
            user_id=read.user_id,
            role=read.role,
            difficulty=read.difficulty,
            status=read.status,
            in_progress=read.in_progress,
            running_score=read.running_score,
            overall_feedback=read.overall_feedback,
            history=read.history,
            created_at=read.created_at,
            updated_at=read.updated_at,
        )

    def complete_session(
        self,
        session_id: int,
        *,
        overall_feedback: str | None = None,
    ) -> InterviewRead | None:
        """Mark session completed and persist final feedback (P7-05)."""
        session = self.get_session(session_id)
        if not session:
            return None
        state = interview_session_to_state(session)
        state['status'] = 'completed'
        if overall_feedback is not None and overall_feedback.strip():
            state['overall_feedback'] = overall_feedback.strip()
        elif not state.get('overall_feedback'):
            score = state.get('running_score')
            count = state.get('score_count') or 0
            if score is not None and count:
                state['overall_feedback'] = (
                    f'Session complete. Average score {score}/10 across {count} answered turn(s).'
                )
            else:
                state['overall_feedback'] = 'Session complete.'
        return self.save_state(session_id, state)

    def abandon_session(self, session_id: int) -> InterviewRead | None:
        session = self.get_session(session_id)
        if not session:
            return None
        state = interview_session_to_state(session)
        state['status'] = 'abandoned'
        if not state.get('overall_feedback'):
            state['overall_feedback'] = 'Session abandoned.'
        return self.save_state(session_id, state)

    def _to_read(
        self,
        session: models.InterviewSession,
        *,
        state: InterviewGraphState | None = None,
    ) -> InterviewRead:
        state = state or interview_session_to_state(session)
        history = [
            InterviewTurnSchema.model_validate(t) for t in (state.get('history') or [])
        ]
        return InterviewRead(
            id=session.id,
            user_id=session.user_id,
            cv_id=session.cv_id,
            role=session.role,
            difficulty=session.difficulty,
            status=session.status or 'pending',
            in_progress=bool(session.in_progress),
            history=history,
            running_score=session.running_score,
            overall_feedback=session.overall_feedback,
            current_question=state.get('current_question'),
            latest_feedback=state.get('latest_feedback'),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )

    def state_payload(self, session_id: int) -> InterviewStateRead | None:
        state = self.load_state(session_id)
        if state is None:
            return None
        return InterviewStateRead.model_validate(state)
