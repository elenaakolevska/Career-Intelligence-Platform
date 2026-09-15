"""Report Agent (P6-07): synthesize upstream agent outputs into final_report.

Does not re-run matching, trend aggregation, or roadmap generation — only
assembles what is already on the shared state and marks missing sections.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.agents.state import CareerGraphState, append_node_log
from app.services.citations import validate_citations

logger = logging.getLogger(__name__)

REPORT_SECTIONS = (
    'cv_summary',
    'ats',
    'top_matches',
    'market_trends',
    'skill_gaps',
    'learning_roadmap',
    'insights',
    'sources',
    'missing_sections',
    'meta',
)


def _resolve_sources(narratives: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate narrative citations against retrieved context and dedupe.

    Returns (insights, sources). A citation ref is only kept when its
    ``source:id`` (or ``source:doc_id``) matches an item actually present in
    that narrative's retrieved ``context_items``. Sources are canonicalized to
    ``source:doc_id`` and deduplicated across all insights.
    """
    sources_by_ref: dict[str, dict[str, Any]] = {}
    insights: list[dict[str, Any]] = []

    for narrative in narratives or []:
        valid, _invalid = validate_citations(
            narrative.get('citations'),
            narrative.get('context_items'),
        )
        cited_refs: list[str] = []
        for canonical in valid:
            sources_by_ref.setdefault(canonical['ref'], canonical)
            cited_refs.append(canonical['ref'])

        insights.append(
            {
                'skill': narrative.get('skill'),
                'priority': narrative.get('priority'),
                'answer': narrative.get('answer'),
                'grounded': narrative.get('grounded'),
                'empty_context': narrative.get('empty_context'),
                'citations': cited_refs,
                'sources': [sources_by_ref[r] for r in cited_refs],
            }
        )

    return insights, list(sources_by_ref.values())


def _section_or_missing(value: Any, *, empty_kinds=(None, '', [], {})) -> tuple[Any, bool]:
    """Return (payload, is_present)."""
    if value in empty_kinds:
        return None, False
    return value, True


def build_final_report(state: CareerGraphState) -> dict[str, Any]:
    missing: list[str] = []

    cv_summary, has_summary = _section_or_missing(state.get('cv_summary'))
    if not has_summary:
        missing.append('cv_summary')

    structured = state.get('structured_cv')
    ats_score = state.get('ats_score')
    ats_issues = state.get('ats_issues')
    has_ats = ats_score is not None or bool(ats_issues)
    if not has_ats:
        missing.append('ats')

    ranked = state.get('ranked_jobs') or []
    top_matches = ranked[:10] if ranked else None
    if not ranked:
        missing.append('top_matches')

    trends = state.get('market_trends')
    has_trends = bool(trends) and bool((trends or {}).get('top_skills') or trends.get('job_count'))
    if not has_trends:
        missing.append('market_trends')
        trends_payload = None
    else:
        trends_payload = trends

    gaps = state.get('skill_gaps')
    if gaps is None:
        missing.append('skill_gaps')
        gaps_payload = None
    else:
        gaps_payload = gaps  # empty list is a valid "no gaps" result

    roadmap = state.get('learning_roadmap')
    if not roadmap:
        missing.append('learning_roadmap')
        roadmap_payload = None
    else:
        roadmap_payload = roadmap

    insights, sources = _resolve_sources(state.get('retrieval_narratives'))

    report = {
        'cv_summary': {
            'text': cv_summary,
            'structured_cv': structured if structured else None,
            'available': has_summary,
        },
        'ats': {
            'score': ats_score,
            'issues': ats_issues or [],
            'available': has_ats,
        },
        'top_matches': {
            'jobs': top_matches or [],
            'count': len(ranked),
            'available': bool(ranked),
        },
        'market_trends': {
            'data': trends_payload,
            'available': bool(has_trends),
        },
        'skill_gaps': {
            'gaps': gaps_payload if gaps_payload is not None else [],
            'count': len(gaps_payload or []),
            'available': gaps is not None,
        },
        'learning_roadmap': {
            'roadmap': roadmap_payload,
            'available': bool(roadmap),
        },
        'insights': insights,
        'sources': sources,
        'missing_sections': missing,
        'meta': {
            'cv_id': state.get('cv_id'),
            'user_id': state.get('user_id'),
            'warnings': list(state.get('warnings') or []),
            'complete': len(missing) == 0,
        },
    }
    return report


def run_report_agent(state: CareerGraphState, db: Session | None = None) -> dict[str, Any]:
    del db
    logger.info('report_agent start cv_id=%s', state.get('cv_id'))
    report = build_final_report(state)
    missing = report.get('missing_sections') or []

    warnings = list(state.get('warnings') or [])
    if missing:
        warnings.append(
            'report_agent: missing upstream sections noted (not fabricated): ' + ', '.join(missing)
        )

    update = append_node_log(
        state,
        'report_agent',
        {
            'event': 'completed',
            'output_keys': ['final_report'],
            'missing_sections': missing,
            'complete': report['meta']['complete'],
            'insight_count': len(report['insights']),
            'source_count': len(report['sources']),
        },
    )
    update.update(
        {
            'final_report': report,
            'warnings': warnings,
            'status': 'running',
        }
    )
    logger.info('report_agent end complete=%s missing=%s', report['meta']['complete'], missing)
    return update


def make_report_agent_node(
    db: Session | None = None,
) -> Callable[[CareerGraphState], dict[str, Any]]:
    def report_agent_node(state: CareerGraphState) -> dict[str, Any]:
        return run_report_agent(state, db)

    return report_agent_node
