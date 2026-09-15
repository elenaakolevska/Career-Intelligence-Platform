"""Shared LangGraph state for the multi-agent career intelligence workflow.

Field ownership (who writes):
| Field                 | Owner (writing agent)      | Notes                                      |
|-----------------------|----------------------------|--------------------------------------------|
| cv_id, user_id        | Orchestrator / API         | Input seed; immutable during a run         |
| errors, warnings      | Any node                   | Append-only diagnostics                    |
| node_log              | Graph runtime helpers      | Append-only execution trace                |
| cv_summary            | CV Agent (P6-02)           | Normalized profile summary                 |
| structured_cv         | CV Agent (P6-02)           | Structured extraction snapshot             |
| ats_score, ats_issues | CV Agent (P6-02)           | From Phase 2 ATS scoring                   |
| ranked_jobs           | Job Matching Agent (P6-03) | Similarity / rerank results                |
| retrieval_context     | Retrieval Agent (P6-10)    | Grounded chunks + provenance               |
| market_trends         | Market Trends Agent (P6-04)| Demand stats from matched jobs             |
| skill_gaps            | Skill Gap Agent (P6-05)    | Prioritized missing skills                 |
| learning_roadmap      | Learning Path Agent (P6-06)| 30/60/90 plan                              |
| final_report          | Report Agent (P6-07)       | Synthesized career report                  |
| status                | Orchestrator / last node   | pending | running | completed | failed     |

State is JSON-serializable (dicts/lists/primitives only) for logging and debug dumps.
"""

from __future__ import annotations

import json
from typing import Any, Literal, NotRequired, TypedDict


AgentStatus = Literal['pending', 'running', 'completed', 'failed']


class CareerGraphState(TypedDict):
    """Shared state all Phase-6 agents read/write via LangGraph."""

    # --- inputs (orchestrator) ---
    cv_id: NotRequired[int | None]
    user_id: NotRequired[int | None]
    status: NotRequired[AgentStatus]

    # --- CV Agent ---
    cv_summary: NotRequired[str | None]
    structured_cv: NotRequired[dict[str, Any] | None]
    ats_score: NotRequired[int | None]
    ats_issues: NotRequired[list[dict[str, Any]] | None]

    # --- Job Matching Agent ---
    ranked_jobs: NotRequired[list[dict[str, Any]] | None]

    # --- Retrieval Agent ---
    retrieval_context: NotRequired[list[dict[str, Any]] | None]
    retrieval_requests: NotRequired[list[dict[str, Any]] | None]
    retrieval_narratives: NotRequired[list[dict[str, Any]] | None]
    sources: NotRequired[list[dict[str, Any]] | None]

    # --- Market Trends Agent ---
    market_trends: NotRequired[dict[str, Any] | None]

    # --- Skill Gap Agent ---
    skill_gaps: NotRequired[list[dict[str, Any]] | None]

    # --- Learning Path Agent ---
    learning_roadmap: NotRequired[dict[str, Any] | None]

    # --- Report Agent ---
    final_report: NotRequired[dict[str, Any] | None]

    # --- shared diagnostics (append-only) ---
    errors: NotRequired[list[str]]
    warnings: NotRequired[list[str]]
    node_log: NotRequired[list[dict[str, Any]]]
    halted: NotRequired[bool]


# Documented owner map (kept in code for tests / tooling)
STATE_FIELD_OWNERS: dict[str, str] = {
    'cv_id': 'orchestrator',
    'user_id': 'orchestrator',
    'status': 'orchestrator',
    'cv_summary': 'cv_agent',
    'structured_cv': 'cv_agent',
    'ats_score': 'cv_agent',
    'ats_issues': 'cv_agent',
    'ranked_jobs': 'job_matching_agent',
    'retrieval_context': 'retrieval_agent',
    'retrieval_requests': 'any',  # enqueued by requesting agents; cleared by retrieval_agent
    'retrieval_narratives': 'retrieval_agent',
    'sources': 'retrieval_agent',
    'market_trends': 'market_trends_agent',
    'skill_gaps': 'skill_gap_agent',
    'learning_roadmap': 'learning_path_agent',
    'final_report': 'report_agent',
    'errors': 'any',
    'warnings': 'any',
    'node_log': 'runtime',
    'halted': 'runtime',
}


def initial_state(*, cv_id: int | None = None, user_id: int | None = None) -> CareerGraphState:
    return {
        'cv_id': cv_id,
        'user_id': user_id,
        'status': 'pending',
        'cv_summary': None,
        'structured_cv': None,
        'ats_score': None,
        'ats_issues': None,
        'ranked_jobs': None,
        'retrieval_context': None,
        'retrieval_requests': [],
        'retrieval_narratives': [],
        'sources': [],
        'market_trends': None,
        'skill_gaps': None,
        'learning_roadmap': None,
        'final_report': None,
        'errors': [],
        'warnings': [],
        'node_log': [],
        'halted': False,
    }


def serialize_state(state: CareerGraphState) -> str:
    """JSON dump for logging/debugging (acceptance: serializable state)."""
    return json.dumps(state, default=str, sort_keys=True)


def deserialize_state(payload: str) -> CareerGraphState:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError('State payload must be a JSON object')
    return data  # type: ignore[return-value]


def append_node_log(state: CareerGraphState, node: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a partial state update that appends a node_log entry."""
    entry = {'node': node, **(detail or {})}
    existing = list(state.get('node_log') or [])
    existing.append(entry)
    return {'node_log': existing}
