"""Interview session state (P7-01) — analogous to CareerGraphState (P6-01).

Field ownership:
| Field              | Owner                         | Notes                                      |
|--------------------|-------------------------------|--------------------------------------------|
| session_id         | Orchestrator / DB             | Set after InterviewSession is persisted    |
| user_id, cv_id     | API / orchestrator            | Session seed; immutable during a run       |
| target_role        | API / Question Agent          | Role under interview (e.g. Junior Java)    |
| difficulty         | API / Question Agent          | junior | mid | senior                      |
| status             | Orchestrator / finish node    | pending | active | completed | abandoned  |
| history            | Question + Evaluate agents    | Ordered Q&A turns with scores/feedback     |
| current_question   | Question Agent (P7-02)        | Latest unanswered prompt                   |
| running_score      | Evaluate Agent (P7-03)        | Rolling average of turn scores             |
| score_count        | Evaluate Agent                | Number of scored turns                     |
| latest_feedback    | Evaluate Agent                | Feedback for the most recent answer        |
| overall_feedback   | Report / finish               | End-of-session summary                     |
| errors, warnings   | Any node                      | Append-only diagnostics                    |
| node_log           | Graph runtime                 | Append-only execution trace                |

State is JSON-serializable for logging, WebSocket payloads, and DB snapshots (resume).
"""

from __future__ import annotations

import json
from typing import Any, Literal, NotRequired, TypedDict

InterviewStatus = Literal['pending', 'active', 'completed', 'abandoned']
InterviewDifficulty = Literal['junior', 'mid', 'senior']


class InterviewTurn(TypedDict):
    """One question/answer/feedback cycle."""

    turn_index: int
    question: str
    answer: NotRequired[str | None]
    score: NotRequired[float | None]  # 0–10 scale (P7-03)
    feedback: NotRequired[str | None]
    difficulty: NotRequired[str | None]
    topics: NotRequired[list[str] | None]
    asked_at: NotRequired[str | None]  # ISO-8601
    answered_at: NotRequired[str | None]


class InterviewGraphState(TypedDict):
    """Shared LangGraph state for the interview simulator."""

    session_id: NotRequired[int | None]
    user_id: NotRequired[int | None]
    cv_id: NotRequired[int | None]
    target_role: NotRequired[str | None]
    difficulty: NotRequired[InterviewDifficulty | str | None]
    status: NotRequired[InterviewStatus]

    history: NotRequired[list[InterviewTurn]]
    current_question: NotRequired[str | None]

    running_score: NotRequired[float | None]
    score_count: NotRequired[int]
    latest_feedback: NotRequired[str | None]
    overall_feedback: NotRequired[str | None]

    errors: NotRequired[list[str]]
    warnings: NotRequired[list[str]]
    node_log: NotRequired[list[dict[str, Any]]]
    # One-shot input for evaluate_agent when running a full turn graph (P7-03)
    pending_answer: NotRequired[str | None]


INTERVIEW_STATE_FIELD_OWNERS: dict[str, str] = {
    'session_id': 'orchestrator',
    'user_id': 'orchestrator',
    'cv_id': 'orchestrator',
    'target_role': 'orchestrator',
    'difficulty': 'question_agent',
    'status': 'orchestrator',
    'history': 'question_agent+evaluate_agent',
    'current_question': 'question_agent',
    'running_score': 'evaluate_agent',
    'score_count': 'evaluate_agent',
    'latest_feedback': 'evaluate_agent',
    'overall_feedback': 'orchestrator',
    'errors': 'any',
    'warnings': 'any',
    'node_log': 'runtime',
    'pending_answer': 'orchestrator',
}


def initial_interview_state(
    *,
    user_id: int | None = None,
    cv_id: int | None = None,
    target_role: str | None = None,
    difficulty: str | None = 'junior',
    session_id: int | None = None,
) -> InterviewGraphState:
    return {
        'session_id': session_id,
        'user_id': user_id,
        'cv_id': cv_id,
        'target_role': target_role,
        'difficulty': difficulty or 'junior',
        'status': 'pending',
        'history': [],
        'current_question': None,
        'running_score': None,
        'score_count': 0,
        'latest_feedback': None,
        'overall_feedback': None,
        'errors': [],
        'warnings': [],
        'node_log': [],
    }


def serialize_interview_state(state: InterviewGraphState) -> str:
    return json.dumps(state, ensure_ascii=False, default=str)


def deserialize_interview_state(payload: str | dict[str, Any]) -> InterviewGraphState:
    data = json.loads(payload) if isinstance(payload, str) else dict(payload)
    return InterviewGraphState(**data)  # type: ignore[misc]


def append_interview_node_log(
    state: InterviewGraphState,
    node: str,
    details: dict[str, Any] | None = None,
) -> InterviewGraphState:
    log = list(state.get('node_log') or [])
    entry = {'node': node, **(details or {})}
    log.append(entry)
    return {**state, 'node_log': log}


def recompute_running_score(history: list[InterviewTurn] | None) -> tuple[float | None, int]:
    scores = [float(t['score']) for t in (history or []) if t.get('score') is not None]
    if not scores:
        return None, 0
    return round(sum(scores) / len(scores), 2), len(scores)


def append_turn(
    state: InterviewGraphState,
    *,
    question: str,
    answer: str | None = None,
    score: float | None = None,
    feedback: str | None = None,
    difficulty: str | None = None,
    topics: list[str] | None = None,
    asked_at: str | None = None,
    answered_at: str | None = None,
) -> InterviewGraphState:
    """Append a Q&A turn and refresh running score (used by later P7 agents)."""
    history = list(state.get('history') or [])
    turn: InterviewTurn = {
        'turn_index': len(history),
        'question': question,
        'answer': answer,
        'score': score,
        'feedback': feedback,
        'difficulty': difficulty or state.get('difficulty'),
        'topics': topics,
        'asked_at': asked_at,
        'answered_at': answered_at,
    }
    history.append(turn)
    running, count = recompute_running_score(history)
    status = state.get('status')
    if status in {None, 'pending', 'active'}:
        status = 'active'
    update: InterviewGraphState = {
        **state,
        'history': history,
        'running_score': running,
        'score_count': count,
        'latest_feedback': feedback if feedback is not None else state.get('latest_feedback'),
        'status': status,  # type: ignore[typeddict-item]
    }
    if answer is None:
        update['current_question'] = question
    else:
        update['current_question'] = None
    return update


def find_pending_turn_index(history: list[InterviewTurn] | None) -> int | None:
    """Index of the latest unanswered question, if any."""
    for i in range(len(history or []) - 1, -1, -1):
        turn = (history or [])[i]
        if turn.get('question') and not turn.get('answer'):
            return i
    return None


def apply_evaluation_to_pending_turn(
    state: InterviewGraphState,
    *,
    answer: str,
    score: float,
    feedback: str,
    answered_at: str | None = None,
) -> InterviewGraphState:
    """Fill the pending unanswered turn with answer + score + feedback (P7-03)."""
    history = list(state.get('history') or [])
    idx = find_pending_turn_index(history)
    if idx is None:
        raise ValueError('No pending unanswered question to evaluate')

    score_clamped = max(0.0, min(10.0, float(score)))
    turn = dict(history[idx])
    turn['answer'] = answer
    turn['score'] = score_clamped
    turn['feedback'] = feedback
    turn['answered_at'] = answered_at
    history[idx] = turn  # type: ignore[call-overload]

    running, count = recompute_running_score(history)
    status = state.get('status')
    if status in {None, 'pending'}:
        status = 'active'
    return {
        **state,
        'history': history,  # type: ignore[typeddict-item]
        'current_question': None,
        'running_score': running,
        'score_count': count,
        'latest_feedback': feedback,
        'status': status,  # type: ignore[typeddict-item]
    }
