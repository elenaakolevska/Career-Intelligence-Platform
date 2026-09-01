"""Interview LangGraph — bootstrap, question, evaluate (P7-01…P7-03)."""

from __future__ import annotations

from typing import Any

from app.interview.evaluate_agent import run_evaluate_agent
from app.interview.question_agent import run_question_agent
from app.interview.state import (
    InterviewGraphState,
    append_interview_node_log,
    initial_interview_state,
)


def _noop_bootstrap(state: InterviewGraphState) -> dict[str, Any]:
    update = append_interview_node_log(state, 'noop_bootstrap', {'event': 'start'})
    update['status'] = 'active'
    return update


def _question_node(state: InterviewGraphState) -> dict[str, Any]:
    """LangGraph node wrapper — DB/LLM injected later via service for persistence."""
    return run_question_agent(state)


def _evaluate_node(state: InterviewGraphState) -> dict[str, Any]:
    """Expects ``pending_answer`` on state (set by caller / tests)."""
    answer = str(state.get('pending_answer') or '')  # type: ignore[arg-type]
    updated = run_evaluate_agent(state, answer=answer)
    cleaned = dict(updated)
    cleaned.pop('pending_answer', None)
    return cleaned


def _noop_finish(state: InterviewGraphState) -> dict[str, Any]:
    update = append_interview_node_log(state, 'noop_finish', {'event': 'done'})
    if state.get('status') not in {'completed', 'abandoned'}:
        update['status'] = 'active'
    return update


def build_noop_interview_graph():
    """Compile bootstrap → finish (P7-01 smoke graph without LLM)."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('langgraph is required for interview graphs') from exc

    graph = StateGraph(InterviewGraphState)
    graph.add_node('noop_bootstrap', _noop_bootstrap)
    graph.add_node('noop_finish', _noop_finish)
    graph.set_entry_point('noop_bootstrap')
    graph.add_edge('noop_bootstrap', 'noop_finish')
    graph.add_edge('noop_finish', END)
    return graph.compile()


def build_interview_question_graph():
    """Compile bootstrap → question_agent (P7-02)."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('langgraph is required for interview graphs') from exc

    graph = StateGraph(InterviewGraphState)
    graph.add_node('noop_bootstrap', _noop_bootstrap)
    graph.add_node('question_agent', _question_node)
    graph.set_entry_point('noop_bootstrap')
    graph.add_edge('noop_bootstrap', 'question_agent')
    graph.add_edge('question_agent', END)
    return graph.compile()


def build_interview_turn_graph():
    """Compile bootstrap → question → evaluate (P7-02/03; needs pending_answer)."""
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('langgraph is required for interview graphs') from exc

    graph = StateGraph(InterviewGraphState)
    graph.add_node('noop_bootstrap', _noop_bootstrap)
    graph.add_node('question_agent', _question_node)
    graph.add_node('evaluate_agent', _evaluate_node)
    graph.set_entry_point('noop_bootstrap')
    graph.add_edge('noop_bootstrap', 'question_agent')
    graph.add_edge('question_agent', 'evaluate_agent')
    graph.add_edge('evaluate_agent', END)
    return graph.compile()


def run_noop_interview_graph(
    *,
    user_id: int | None = None,
    cv_id: int | None = None,
    target_role: str | None = None,
    difficulty: str | None = 'junior',
) -> InterviewGraphState:
    graph = build_noop_interview_graph()
    seed = initial_interview_state(
        user_id=user_id,
        cv_id=cv_id,
        target_role=target_role,
        difficulty=difficulty,
    )
    return graph.invoke(seed)


def run_interview_question_graph(
    *,
    user_id: int | None = None,
    cv_id: int | None = None,
    target_role: str | None = None,
    difficulty: str | None = 'junior',
) -> InterviewGraphState:
    graph = build_interview_question_graph()
    seed = initial_interview_state(
        user_id=user_id,
        cv_id=cv_id,
        target_role=target_role,
        difficulty=difficulty,
    )
    return graph.invoke(seed)


def run_interview_turn_graph(
    *,
    answer: str,
    user_id: int | None = None,
    cv_id: int | None = None,
    target_role: str | None = None,
    difficulty: str | None = 'junior',
) -> InterviewGraphState:
    graph = build_interview_turn_graph()
    seed = initial_interview_state(
        user_id=user_id,
        cv_id=cv_id,
        target_role=target_role,
        difficulty=difficulty,
    )
    seed['pending_answer'] = answer  # type: ignore[typeddict-unknown-key]
    return graph.invoke(seed)
