"""Skill Gap Agent (P6-05): compare candidate skills vs market demand."""

from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.agents.skill_utils import (
    candidate_skill_set,
    extract_skills_from_text,
    skills_match,
)
from app.agents.state import CareerGraphState, append_node_log

logger = logging.getLogger(__name__)

# Contract for Learning Path Agent (P6-06)
SKILL_GAP_KEYS = (
    'skill',
    'priority',
    'demand_pct',
    'mention_count',
    'reason',
)


def _priority_from_demand(pct: float, *, sample_too_small: bool) -> str:
    if sample_too_small:
        # Soften priorities when stats are unreliable
        if pct >= 50:
            return 'medium'
        return 'low'
    if pct >= 60:
        return 'high'
    if pct >= 30:
        return 'medium'
    return 'low'


def compute_skill_gaps(
    *,
    candidate_skills: list[str] | None,
    market_trends: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    trends = market_trends or {}
    top_skills = list(trends.get('top_skills') or [])
    sample_too_small = bool(trends.get('sample_too_small'))
    owned = candidate_skill_set(candidate_skills or [])

    gaps: list[dict[str, Any]] = []
    for entry in top_skills:
        skill = str(entry.get('skill') or '').strip()
        if not skill:
            continue
        if skills_match(skill, owned):
            continue
        pct = float(entry.get('pct_of_postings') or 0.0)
        count = int(entry.get('mention_count') or 0)
        priority = _priority_from_demand(pct, sample_too_small=sample_too_small)
        gaps.append(
            {
                'skill': skill,
                'priority': priority,
                'demand_pct': pct,
                'mention_count': count,
                'reason': (
                    f'Appears in {pct}% of matched postings ({count}/{trends.get("job_count", "?")}) '
                    f'and is not evidenced in the candidate profile'
                    + (' [small sample]' if sample_too_small else '')
                ),
            }
        )

    priority_rank = {'high': 0, 'medium': 1, 'low': 2}
    gaps.sort(key=lambda g: (priority_rank.get(g['priority'], 9), -g['demand_pct'], g['skill']))
    return gaps


def _candidate_skills_from_state(state: CareerGraphState) -> list[str]:
    """Collect candidate skills from structured CV, with summary-text fallback."""
    collected: list[str] = []
    structured = state.get('structured_cv') or {}
    if isinstance(structured, dict):
        skills = structured.get('skills')
        if isinstance(skills, list):
            collected.extend(str(s) for s in skills if str(s).strip())
        # Also mine free-text summary / experience blurbs when present
        for key in ('summary',):
            if structured.get(key):
                collected.extend(extract_skills_from_text(str(structured[key])))
        for exp in structured.get('experience') or []:
            if isinstance(exp, dict):
                blob = ' '.join(str(exp.get(k) or '') for k in ('title', 'description'))
                collected.extend(extract_skills_from_text(blob))

    summary = state.get('cv_summary') or ''
    if summary:
        collected.extend(extract_skills_from_text(summary))

    # De-dupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for skill in collected:
        key = skill.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(skill.strip())
    return unique


def run_skill_gap_agent(state: CareerGraphState, db: Session | None = None) -> dict[str, Any]:
    del db
    candidate_skills = _candidate_skills_from_state(state)
    trends = state.get('market_trends')
    logger.info(
        'skill_gap_agent start candidate_skills=%s market_skills=%s',
        len(candidate_skills),
        len((trends or {}).get('top_skills') or []),
    )

    warnings = list(state.get('warnings') or [])
    if not trends or not (trends.get('top_skills') or []):
        warnings.append('skill_gap_agent: no market trend skills; skill_gaps=[]')
        gaps: list[dict[str, Any]] = []
    else:
        gaps = compute_skill_gaps(candidate_skills=candidate_skills, market_trends=trends)

    update = append_node_log(
        state,
        'skill_gap_agent',
        {
            'event': 'completed',
            'input': {
                'candidate_skill_count': len(candidate_skills),
                'market_skill_count': len((trends or {}).get('top_skills') or []),
            },
            'output_keys': ['skill_gaps'],
            'gap_count': len(gaps),
        },
    )
    update.update(
        {
            'skill_gaps': gaps,
            'retrieval_requests': [
                {
                    'query': f"{g['skill']} learning course tutorial book",
                    'requesting_agent': 'skill_gap_agent',
                    'sources': ['resources'],
                    'top_k': 3,
                    'skill': g['skill'],
                }
                for g in gaps[:8]
                if g.get('skill')
            ],
            'warnings': warnings,
            'status': 'running',
        }
    )
    logger.info('skill_gap_agent end gaps=%s', len(gaps))
    return update


def make_skill_gap_agent_node(
    db: Session | None = None,
) -> Callable[[CareerGraphState], dict[str, Any]]:
    def skill_gap_agent_node(state: CareerGraphState) -> dict[str, Any]:
        return run_skill_gap_agent(state, db)

    return skill_gap_agent_node
