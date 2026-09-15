"""P6-08 career workflow orchestration: ordering, failure policy, timing, diffs.

## Node failure policy

| Node                 | Policy     | Behavior on exception                                      |
|----------------------|------------|------------------------------------------------------------|
| cv_agent             | halt       | Mark `halted=True`, skip remaining specialists, still try  |
|                      |            | `report_agent` then finish (partial report if possible).   |
| job_matching_agent   | continue   | Log error, set `ranked_jobs=[]`, proceed                   |
| market_trends_agent  | continue   | Log error, set empty trends, proceed                       |
| skill_gap_agent      | continue   | Log error, set `skill_gaps=[]`, proceed                    |
| retrieval_agent      | continue   | Log error, set `retrieval_context=[]`, proceed             |
| learning_path_agent  | continue   | Log error, set empty roadmap, proceed                      |
| report_agent         | continue   | Log error, leave `final_report` missing, finish            |

Halt vs continue is evaluated inside wrapped nodes. Graph conditional edges
route to `report_agent` (or `noop_finish`) when `halted` is set so the run
does not crash the process.
"""

from __future__ import annotations

import logging
import time
from copy import deepcopy
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agents.cv_agent import make_cv_agent_node
from app.agents.job_matching_agent import make_job_matching_agent_node
from app.agents.learning_path_agent import make_learning_path_agent_node
from app.agents.market_trends_agent import make_market_trends_agent_node
from app.agents.report_agent import make_report_agent_node
from app.agents.retrieval_agent import make_retrieval_agent_node
from app.agents.skill_gap_agent import make_skill_gap_agent_node
from app.agents.state import CareerGraphState, append_node_log, initial_state, serialize_state

logger = logging.getLogger(__name__)

# Documented orchestration order (matches brief §4.4 agent pipeline)
CAREER_GRAPH_ORDER = (
    'noop_bootstrap',
    'cv_agent',
    'job_matching_agent',
    'market_trends_agent',
    'skill_gap_agent',
    'retrieval_agent',
    'learning_path_agent',
    'report_agent',
    'noop_finish',
)

NODE_FAILURE_POLICY: dict[str, str] = {
    'cv_agent': 'halt',
    'job_matching_agent': 'continue',
    'market_trends_agent': 'continue',
    'skill_gap_agent': 'continue',
    'retrieval_agent': 'continue',
    'learning_path_agent': 'continue',
    'report_agent': 'continue',
}

SAFE_DEFAULTS: dict[str, dict[str, Any]] = {
    'job_matching_agent': {'ranked_jobs': []},
    'market_trends_agent': {
        'market_trends': {
            'job_count': 0,
            'sample_too_small': True,
            'top_skills': [],
            'note': 'market_trends_agent failed; stats omitted',
        }
    },
    'skill_gap_agent': {'skill_gaps': []},
    'retrieval_agent': {
        'retrieval_context': [],
        'retrieval_requests': [],
        'retrieval_narratives': [],
        'sources': [],
    },
    'learning_path_agent': {
        'learning_roadmap': {
            'days_30': {'focus': 'Unavailable', 'skills': [], 'resources': []},
            'days_60': {'focus': 'Unavailable', 'skills': [], 'resources': []},
            'days_90': {'focus': 'Unavailable', 'skills': [], 'resources': []},
            'notes': 'learning_path_agent failed; roadmap omitted',
        }
    },
}

TRACKED_KEYS = (
    'status',
    'halted',
    'cv_summary',
    'structured_cv',
    'ats_score',
    'ranked_jobs',
    'market_trends',
    'skill_gaps',
    'learning_roadmap',
    'final_report',
    'retrieval_context',
    'retrieval_narratives',
    'sources',
    'errors',
    'warnings',
)


def _snapshot(state: CareerGraphState) -> dict[str, Any]:
    return {k: deepcopy(state.get(k)) for k in TRACKED_KEYS}


def _state_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for key in TRACKED_KEYS:
        if before.get(key) != after.get(key):
            # Avoid dumping huge blobs in logs — summarize collections
            new_val = after.get(key)
            if isinstance(new_val, list):
                changed[key] = {'type': 'list', 'len': len(new_val)}
            elif isinstance(new_val, dict):
                changed[key] = {'type': 'dict', 'keys': sorted(new_val.keys())}
            elif isinstance(new_val, str) and len(new_val) > 120:
                changed[key] = {'type': 'str', 'chars': len(new_val)}
            else:
                changed[key] = new_val
    return changed


def _merge_state(state: CareerGraphState, update: dict[str, Any]) -> CareerGraphState:
    merged: dict[str, Any] = dict(state)
    merged.update(update)
    return merged  # type: ignore[return-value]


def wrap_agent_node(
    name: str,
    node_fn: Callable[[CareerGraphState], dict[str, Any]],
) -> Callable[[CareerGraphState], dict[str, Any]]:
    """Wrap a node with timing, state-diff logging, and failure policy."""

    policy = NODE_FAILURE_POLICY.get(name, 'continue')

    def wrapped(state: CareerGraphState) -> dict[str, Any]:
        if state.get('halted') and name not in {'report_agent', 'noop_finish', 'noop_bootstrap'}:
            # Skipped due to prior halt — record and no-op
            update = append_node_log(state, name, {'event': 'skipped', 'reason': 'halted_upstream'})
            return update

        before = _snapshot(state)
        started = time.perf_counter()
        try:
            update = node_fn(state) or {}
            elapsed_ms = (time.perf_counter() - started) * 1000
            merged = _merge_state(state, update)
            after = _snapshot(merged)
            diff = _state_diff(before, after)
            # Ensure node_log carries diff + timing on the latest entry
            log = list(merged.get('node_log') or update.get('node_log') or state.get('node_log') or [])
            if log and log[-1].get('node') == name:
                log[-1] = {**log[-1], 'duration_ms': round(elapsed_ms, 2), 'state_diff': diff}
            else:
                log.append(
                    {
                        'node': name,
                        'event': 'completed',
                        'duration_ms': round(elapsed_ms, 2),
                        'state_diff': diff,
                    }
                )
            update = {**update, 'node_log': log}
            logger.info(
                'workflow node=%s event=ok duration_ms=%.2f diff_keys=%s',
                name,
                elapsed_ms,
                list(diff.keys()),
            )
            return update
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.exception('workflow node=%s failed policy=%s', name, policy)
            errors = list(state.get('errors') or [])
            warnings = list(state.get('warnings') or [])
            errors.append(f'{name}: {exc}')
            update = append_node_log(
                state,
                name,
                {
                    'event': 'error',
                    'policy': policy,
                    'error': str(exc),
                    'duration_ms': round(elapsed_ms, 2),
                },
            )
            update['errors'] = errors
            update['warnings'] = warnings

            if policy == 'halt':
                warnings.append(f'{name} failed with halt policy; skipping remaining specialist nodes')
                update['warnings'] = warnings
                update['halted'] = True
                update['status'] = 'failed'
                return update

            warnings.append(f'{name} failed with continue policy; applying safe defaults')
            update['warnings'] = warnings
            update.update(SAFE_DEFAULTS.get(name, {}))
            update['status'] = 'running'
            return update

    return wrapped


def noop_bootstrap(state: CareerGraphState) -> dict[str, Any]:
    update = append_node_log(state, 'noop_bootstrap', {'event': 'start'})
    update['status'] = 'running'
    update['halted'] = False
    return update


def noop_finish(state: CareerGraphState) -> dict[str, Any]:
    update = append_node_log(state, 'noop_finish', {'event': 'done'})
    if state.get('halted') and state.get('status') == 'failed':
        # Keep failed if halted before a usable report
        if not state.get('final_report'):
            update['status'] = 'failed'
        else:
            update['status'] = 'completed'
    else:
        update['status'] = 'completed'
    return update


def _route_after_cv(state: CareerGraphState) -> str:
    return 'report_agent' if state.get('halted') else 'job_matching_agent'


def _route_after_jobs(state: CareerGraphState) -> str:
    return 'report_agent' if state.get('halted') else 'market_trends_agent'


def _route_after_trends(state: CareerGraphState) -> str:
    return 'report_agent' if state.get('halted') else 'skill_gap_agent'


def _route_after_gaps(state: CareerGraphState) -> str:
    return 'report_agent' if state.get('halted') else 'retrieval_agent'


def _route_after_retrieval(state: CareerGraphState) -> str:
    return 'report_agent' if state.get('halted') else 'learning_path_agent'


def build_career_graph(db: Session):
    """Compile the full multi-agent career intelligence graph (P6-08 + P6-10)."""
    graph = StateGraph(CareerGraphState)

    graph.add_node('noop_bootstrap', wrap_agent_node('noop_bootstrap', noop_bootstrap))
    graph.add_node('cv_agent', wrap_agent_node('cv_agent', make_cv_agent_node(db)))
    graph.add_node(
        'job_matching_agent',
        wrap_agent_node('job_matching_agent', make_job_matching_agent_node(db)),
    )
    graph.add_node(
        'market_trends_agent',
        wrap_agent_node('market_trends_agent', make_market_trends_agent_node(db)),
    )
    graph.add_node(
        'skill_gap_agent',
        wrap_agent_node('skill_gap_agent', make_skill_gap_agent_node(db)),
    )
    graph.add_node(
        'retrieval_agent',
        wrap_agent_node('retrieval_agent', make_retrieval_agent_node(db)),
    )
    graph.add_node(
        'learning_path_agent',
        wrap_agent_node('learning_path_agent', make_learning_path_agent_node(db)),
    )
    graph.add_node('report_agent', wrap_agent_node('report_agent', make_report_agent_node(db)))
    graph.add_node('noop_finish', wrap_agent_node('noop_finish', noop_finish))

    graph.add_edge(START, 'noop_bootstrap')
    graph.add_edge('noop_bootstrap', 'cv_agent')
    graph.add_conditional_edges('cv_agent', _route_after_cv, {
        'job_matching_agent': 'job_matching_agent',
        'report_agent': 'report_agent',
    })
    graph.add_conditional_edges('job_matching_agent', _route_after_jobs, {
        'market_trends_agent': 'market_trends_agent',
        'report_agent': 'report_agent',
    })
    graph.add_conditional_edges('market_trends_agent', _route_after_trends, {
        'skill_gap_agent': 'skill_gap_agent',
        'report_agent': 'report_agent',
    })
    graph.add_conditional_edges('skill_gap_agent', _route_after_gaps, {
        'retrieval_agent': 'retrieval_agent',
        'report_agent': 'report_agent',
    })
    graph.add_conditional_edges('retrieval_agent', _route_after_retrieval, {
        'learning_path_agent': 'learning_path_agent',
        'report_agent': 'report_agent',
    })
    graph.add_edge('learning_path_agent', 'report_agent')
    graph.add_edge('report_agent', 'noop_finish')
    graph.add_edge('noop_finish', END)
    return graph.compile()


# Back-compat alias used by earlier tests / callers
def build_analysis_graph(db: Session):
    return build_career_graph(db)


def run_career_workflow(
    db: Session,
    *,
    cv_id: int | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Run the full graph unattended; returns state plus timing metadata."""
    app = build_career_graph(db)
    seed = initial_state(cv_id=cv_id, user_id=user_id)
    seed['halted'] = False  # type: ignore[typeddict-item]

    started = time.perf_counter()
    result = app.invoke(seed)
    total_ms = (time.perf_counter() - started) * 1000

    node_timings = {
        entry.get('node'): entry.get('duration_ms')
        for entry in (result.get('node_log') or [])
        if entry.get('duration_ms') is not None
    }
    logger.info(
        'workflow complete cv_id=%s total_ms=%.2f status=%s halted=%s',
        cv_id,
        total_ms,
        result.get('status'),
        result.get('halted'),
    )
    return {
        'state': result,
        'total_ms': round(total_ms, 2),
        'node_timings_ms': node_timings,
        'node_log': result.get('node_log') or [],
        'serialized_state': serialize_state(result),  # type: ignore[arg-type]
    }


def run_analysis_graph(
    db: Session,
    *,
    cv_id: int | None = None,
    user_id: int | None = None,
) -> CareerGraphState:
    """Back-compat: return final state only."""
    return run_career_workflow(db, cv_id=cv_id, user_id=user_id)['state']  # type: ignore[return-value]
