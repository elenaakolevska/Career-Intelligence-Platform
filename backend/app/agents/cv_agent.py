"""CV Agent (P6-02): load CVProfile and write a normalized summary into graph state."""

from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from app import models
from app.agents.state import CareerGraphState, append_node_log
from app.services.cv_service import CVService

logger = logging.getLogger(__name__)


def build_normalized_cv_summary(
    cv: models.CVProfile | None,
    structured: dict[str, Any] | None = None,
) -> str:
    """Produce a compact, downstream-friendly profile summary.

    Sparse / missing data never raises — returns an explicit placeholder instead.
    """
    if cv is None:
        return 'No CV profile available.'

    data = structured if structured is not None else (CVService.structured_as_dict(cv) or {})
    parts: list[str] = []

    name = data.get('name')
    if name:
        parts.append(f'Candidate: {name}')

    location = data.get('location')
    if location:
        parts.append(f'Location: {location}')

    summary = data.get('summary') or cv.summary
    if summary:
        parts.append(f'Summary: {summary}')

    def _clean_skill(raw: Any) -> str:
        text = str(raw or '').strip()
        for ch in ('\u200b', '\u200c', '\u200d', '\ufeff'):
            text = text.replace(ch, '')
        return text.lstrip('●•▪◦-*–— \t').strip()

    skills = [_clean_skill(s) for s in (data.get('skills') or [])]
    skills = [s for s in skills if s]
    if skills:
        parts.append('Skills:')
        for skill in skills:
            parts.append(f'- {skill}')
    else:
        parts.append('Skills: (none extracted)')

    experience = data.get('experience') or []
    if experience:
        parts.append('Experience:')
        for exp in experience[:5]:
            bits = [exp.get('title'), exp.get('company'), exp.get('start_date'), exp.get('end_date')]
            line = ' | '.join(str(b) for b in bits if b)
            if exp.get('description'):
                line = f'{line} — {exp["description"]}' if line else str(exp['description'])
            if line:
                parts.append(f'- {line}')
    else:
        parts.append('Experience: (none extracted)')

    education = data.get('education') or []
    if education:
        parts.append('Education:')
        for edu in education[:3]:
            bits = [edu.get('degree') or edu.get('field_of_study'), edu.get('institution')]
            line = ' | '.join(str(b) for b in bits if b)
            if line:
                parts.append(f'- {line}')

    if len(parts) <= 1 and cv.raw_text:
        snippet = cv.raw_text.strip()[:800]
        if snippet:
            parts.append(f'Raw excerpt: {snippet}')

    if not parts:
        return 'Sparse CV: no structured or raw content available.'

    return '\n'.join(parts)


def run_cv_agent(state: CareerGraphState, db: Session) -> dict[str, Any]:
    """Core CV agent logic (also usable outside LangGraph)."""
    cv_id = state.get('cv_id')
    logger.info('cv_agent start cv_id=%s', cv_id)

    warnings = list(state.get('warnings') or [])
    errors = list(state.get('errors') or [])

    if cv_id is None:
        summary = 'No CV profile available.'
        update = append_node_log(
            state,
            'cv_agent',
            {'event': 'skipped', 'reason': 'missing_cv_id', 'output_keys': ['cv_summary']},
        )
        warnings.append('cv_agent: missing cv_id; wrote placeholder summary')
        update.update(
            {
                'cv_summary': summary,
                'structured_cv': None,
                'ats_score': None,
                'ats_issues': None,
                'warnings': warnings,
                'status': 'running',
            }
        )
        logger.info('cv_agent end cv_id=None summary_len=%s', len(summary))
        return update

    svc = CVService(db)
    cv = svc.get_cv(int(cv_id))
    if cv is None:
        summary = 'No CV profile available.'
        update = append_node_log(
            state,
            'cv_agent',
            {'event': 'not_found', 'cv_id': cv_id, 'output_keys': ['cv_summary']},
        )
        warnings.append(f'cv_agent: CVProfile {cv_id} not found')
        update.update(
            {
                'cv_summary': summary,
                'structured_cv': None,
                'ats_score': None,
                'ats_issues': None,
                'warnings': warnings,
                'status': 'running',
            }
        )
        logger.info('cv_agent end cv_id=%s not_found', cv_id)
        return update

    structured = CVService.structured_as_dict(cv)
    if not structured:
        warnings.append('cv_agent: no structured_data; summarizing from raw/summary fields')
    if not (cv.raw_text or '').strip() and not structured:
        warnings.append('cv_agent: sparse CV with no raw_text and no structured_data')

    summary = build_normalized_cv_summary(cv, structured)
    ats_issues = CVService.ats_issues_as_list(cv)

    output_keys = ['cv_summary', 'structured_cv', 'ats_score', 'ats_issues']
    update = append_node_log(
        state,
        'cv_agent',
        {
            'event': 'completed',
            'cv_id': cv_id,
            'input': {'status': cv.status, 'has_structured': bool(structured)},
            'output_keys': output_keys,
            'summary_chars': len(summary),
        },
    )
    update.update(
        {
            'cv_summary': summary,
            'structured_cv': structured,
            'ats_score': cv.ats_score,
            'ats_issues': ats_issues,
            'warnings': warnings,
            'errors': errors,
            'status': 'running',
        }
    )
    logger.info(
        'cv_agent end cv_id=%s summary_chars=%s ats_score=%s',
        cv_id,
        len(summary),
        cv.ats_score,
    )
    return update


def make_cv_agent_node(db: Session) -> Callable[[CareerGraphState], dict[str, Any]]:
    """Bind a SQLAlchemy session into a LangGraph-compatible node function."""

    def cv_agent_node(state: CareerGraphState) -> dict[str, Any]:
        return run_cv_agent(state, db)

    return cv_agent_node
