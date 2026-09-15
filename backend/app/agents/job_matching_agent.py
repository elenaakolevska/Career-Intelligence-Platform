"""Job Matching Agent (P6-03): similarity search (+ optional rerank) → ranked_jobs."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from sqlalchemy.orm import Session

from app import models
from app.agents.state import CareerGraphState, append_node_log
from app.core.config import settings
from app.services.jobs_service import JobsService
from app.services.reranker import rerank_jobs
from app.services.similarity_search import search_jobs_for_cv

logger = logging.getLogger(__name__)

# Contract expected by Skill Gap Agent (P6-05) and downstream nodes
RANKED_JOB_KEYS = (
    'job_id',
    'score',
    'title',
    'company',
    'location',
    'url',
    'description',
)

_SENIOR_PATTERNS = re.compile(
    r'\b(senior|staff|principal|lead|manager|director|head of|architect)\b',
    re.I,
)
_JUNIOR_PATTERNS = re.compile(
    r'\b(junior|graduate|entry[\s-]?level|intern|trainee|apprentice|associate)\b',
    re.I,
)


def estimate_candidate_level(structured: dict[str, Any] | None, cv_summary: str = '') -> str:
    """Return 'junior' | 'mid' | 'senior' from CV signals (conservative)."""
    structured = structured or {}
    blob = ' '.join(
        [
            cv_summary or '',
            str(structured.get('summary') or ''),
            ' '.join(str(e.get('title') or '') for e in (structured.get('experience') or [])),
        ]
    ).lower()
    if _SENIOR_PATTERNS.search(blob) and not _JUNIOR_PATTERNS.search(blob):
        return 'senior'
    exp = structured.get('experience') or []
    paid_roles = [
        e
        for e in exp
        if e.get('company')
        and 'project' not in str(e.get('title') or '').lower()
        and 'red cross' not in str(e.get('company') or '').lower()
    ]
    if structured.get('education') and len(paid_roles) <= 1:
        return 'junior'
    if _JUNIOR_PATTERNS.search(blob) or 'student' in blob:
        return 'junior'
    return 'mid'


def apply_seniority_adjustment(
    matches: list[dict[str, Any]],
    *,
    candidate_level: str,
) -> list[dict[str, Any]]:
    """Re-score matches so junior candidates prefer junior/mid roles over Staff/Principal."""
    adjusted: list[dict[str, Any]] = []
    for m in matches:
        title = str(m.get('title') or '')
        desc = str(m.get('description') or '')
        text = f'{title} {desc}'
        score = float(m.get('score') or 0.0)
        item = dict(m)
        if candidate_level == 'junior':
            if _SENIOR_PATTERNS.search(text):
                score *= 0.35
                item['seniority_penalty'] = True
            elif _JUNIOR_PATTERNS.search(text):
                score *= 1.25
                item['seniority_boost'] = True
        elif candidate_level == 'senior':
            if _JUNIOR_PATTERNS.search(text) and not _SENIOR_PATTERNS.search(text):
                score *= 0.7
        item['score'] = score
        adjusted.append(item)
    adjusted.sort(key=lambda x: float(x.get('score') or 0.0), reverse=True)
    return adjusted


def normalize_ranked_job(raw: dict[str, Any]) -> dict[str, Any]:
    """Ensure a stable shape for Skill Gap / Market Trends agents."""
    return {
        'job_id': raw.get('job_id'),
        'score': float(raw.get('score') or 0.0),
        'title': raw.get('title'),
        'company': raw.get('company'),
        'location': raw.get('location'),
        'url': raw.get('url'),
        'description': raw.get('description'),
        'reranked': bool(raw.get('reranked', False)),
    }


def run_job_matching_agent(state: CareerGraphState, db: Session) -> dict[str, Any]:
    cv_id = state.get('cv_id')
    cv_summary = state.get('cv_summary') or ''
    structured = state.get('structured_cv') or {}
    logger.info('job_matching_agent start cv_id=%s summary_chars=%s', cv_id, len(cv_summary))

    warnings = list(state.get('warnings') or [])
    errors = list(state.get('errors') or [])
    ranked: list[dict[str, Any]] = []
    level = 'mid'

    if cv_id is None:
        warnings.append('job_matching_agent: missing cv_id; ranked_jobs=[]')
        update = append_node_log(
            state,
            'job_matching_agent',
            {'event': 'skipped', 'reason': 'missing_cv_id', 'match_count': 0},
        )
        update.update({'ranked_jobs': [], 'warnings': warnings, 'status': 'running'})
        return update

    try:
        jobs_svc = JobsService(db)
        if db.query(models.JobPosting).count() == 0:
            jobs_svc.ensure_corpus_for_cv(cv_id)
            logger.info('job_matching_agent ensured job corpus for cv_id=%s', cv_id)

        top_k = settings.similarity_top_k
        fetch_k = max(top_k * 3, top_k)
        if settings.rerank_enabled:
            fetch_k = max(fetch_k, settings.rerank_top_n)

        matches = search_jobs_for_cv(db, int(cv_id), top_k=fetch_k)
        query_text = cv_summary or f'cv:{cv_id}'
        if settings.rerank_enabled and matches:
            matches = rerank_jobs(query_text, matches)

        level = estimate_candidate_level(structured, cv_summary)
        matches = apply_seniority_adjustment(matches, candidate_level=level)
        matches = matches[:top_k]

        ranked = [normalize_ranked_job(m) for m in matches]
        if not ranked:
            warnings.append(
                'job_matching_agent: zero matches; downstream agents should degrade gracefully'
            )
    except Exception as exc:
        logger.exception('job_matching_agent failed')
        errors.append(f'job_matching_agent: {exc}')
        ranked = []
        warnings.append('job_matching_agent: search failed; ranked_jobs=[]')

    update = append_node_log(
        state,
        'job_matching_agent',
        {
            'event': 'completed',
            'cv_id': cv_id,
            'input': {
                'has_cv_summary': bool(cv_summary),
                'rerank_enabled': settings.rerank_enabled,
                'candidate_level': level,
            },
            'output_keys': ['ranked_jobs'],
            'match_count': len(ranked),
        },
    )
    update.update(
        {
            'ranked_jobs': ranked,
            'warnings': warnings,
            'errors': errors,
            'status': 'running',
        }
    )
    logger.info('job_matching_agent end cv_id=%s matches=%s level=%s', cv_id, len(ranked), level)
    return update


def make_job_matching_agent_node(db: Session) -> Callable[[CareerGraphState], dict[str, Any]]:
    def job_matching_agent_node(state: CareerGraphState) -> dict[str, Any]:
        return run_job_matching_agent(state, db)

    return job_matching_agent_node
