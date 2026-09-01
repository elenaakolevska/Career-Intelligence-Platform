"""LangGraph workflow builders.

Full orchestration with failure policy / timing lives in ``workflow.py`` (P6-08).
This module keeps smaller graphs for incremental agent tests.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.cv_agent import make_cv_agent_node
from app.agents.job_matching_agent import make_job_matching_agent_node
from app.agents.state import CareerGraphState, append_node_log, initial_state
from app.agents.workflow import (
    CAREER_GRAPH_ORDER,
    NODE_FAILURE_POLICY,
    build_career_graph,
    run_analysis_graph,
    run_career_workflow,
)

logger = logging.getLogger(__name__)


def noop_bootstrap(state: CareerGraphState) -> dict[str, Any]:
    logger.info('noop_bootstrap cv_id=%s', state.get('cv_id'))
    update = append_node_log(state, 'noop_bootstrap', {'event': 'start'})
    update['status'] = 'running'
    return update


def noop_finish(state: CareerGraphState) -> dict[str, Any]:
    logger.info('noop_finish cv_id=%s', state.get('cv_id'))
    update = append_node_log(state, 'noop_finish', {'event': 'done'})
    update['status'] = 'completed'
    return update


def build_noop_graph():
    graph = StateGraph(CareerGraphState)
    graph.add_node('noop_bootstrap', noop_bootstrap)
    graph.add_node('noop_finish', noop_finish)
    graph.add_edge(START, 'noop_bootstrap')
    graph.add_edge('noop_bootstrap', 'noop_finish')
    graph.add_edge('noop_finish', END)
    return graph.compile()


def run_noop_graph(*, cv_id: int | None = None, user_id: int | None = None) -> CareerGraphState:
    app = build_noop_graph()
    seed = initial_state(cv_id=cv_id, user_id=user_id)
    result = app.invoke(seed)
    return result  # type: ignore[return-value]


def build_cv_agent_graph(db: Session):
    graph = StateGraph(CareerGraphState)
    graph.add_node('noop_bootstrap', noop_bootstrap)
    graph.add_node('cv_agent', make_cv_agent_node(db))
    graph.add_node('noop_finish', noop_finish)
    graph.add_edge(START, 'noop_bootstrap')
    graph.add_edge('noop_bootstrap', 'cv_agent')
    graph.add_edge('cv_agent', 'noop_finish')
    graph.add_edge('noop_finish', END)
    return graph.compile()


def run_cv_agent_graph(
    db: Session,
    *,
    cv_id: int | None = None,
    user_id: int | None = None,
) -> CareerGraphState:
    app = build_cv_agent_graph(db)
    seed = initial_state(cv_id=cv_id, user_id=user_id)
    result = app.invoke(seed)
    return result  # type: ignore[return-value]


def build_matching_graph(db: Session):
    graph = StateGraph(CareerGraphState)
    graph.add_node('noop_bootstrap', noop_bootstrap)
    graph.add_node('cv_agent', make_cv_agent_node(db))
    graph.add_node('job_matching_agent', make_job_matching_agent_node(db))
    graph.add_node('noop_finish', noop_finish)
    graph.add_edge(START, 'noop_bootstrap')
    graph.add_edge('noop_bootstrap', 'cv_agent')
    graph.add_edge('cv_agent', 'job_matching_agent')
    graph.add_edge('job_matching_agent', 'noop_finish')
    graph.add_edge('noop_finish', END)
    return graph.compile()


def run_matching_graph(
    db: Session,
    *,
    cv_id: int | None = None,
    user_id: int | None = None,
) -> CareerGraphState:
    app = build_matching_graph(db)
    seed = initial_state(cv_id=cv_id, user_id=user_id)
    result = app.invoke(seed)
    return result  # type: ignore[return-value]


def build_analysis_graph(db: Session):
    """Alias for the full P6-08 career graph."""
    return build_career_graph(db)


__all__ = [
    'CAREER_GRAPH_ORDER',
    'NODE_FAILURE_POLICY',
    'build_noop_graph',
    'run_noop_graph',
    'build_cv_agent_graph',
    'run_cv_agent_graph',
    'build_matching_graph',
    'run_matching_graph',
    'build_analysis_graph',
    'build_career_graph',
    'run_analysis_graph',
    'run_career_workflow',
]
