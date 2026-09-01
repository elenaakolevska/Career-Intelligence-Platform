"""Market Trends Agent (P6-04): aggregate in-demand skills from ranked jobs."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.agents.skill_utils import extract_skills_from_text
from app.agents.state import CareerGraphState, append_node_log

logger = logging.getLogger(__name__)

MIN_JOBS_FOR_RELIABLE_STATS = 3


def analyze_market_trends(
    ranked_jobs: list[dict[str, Any]] | None,
    *,
    top_n: int = 15,
) -> dict[str, Any]:
    jobs = list(ranked_jobs or [])
    job_count = len(jobs)

    if job_count == 0:
        return {
            'job_count': 0,
            'sample_too_small': True,
            'top_skills': [],
            'note': 'No matched jobs available; market trend stats omitted.',
        }

    per_job_skills: list[set[str]] = []
    for job in jobs:
        blob = ' '.join(
            str(job.get(k) or '') for k in ('title', 'description', 'company')
        )
        per_job_skills.append(set(extract_skills_from_text(blob)))

    # Count how many postings mention each skill (not raw token frequency)
    mention_counter: Counter[str] = Counter()
    for skills in per_job_skills:
        mention_counter.update(skills)

    top_skills: list[dict[str, Any]] = []
    for skill, count in mention_counter.most_common(top_n):
        pct = round(100.0 * count / job_count, 1)
        top_skills.append(
            {
                'skill': skill,
                'mention_count': int(count),
                'pct_of_postings': pct,
            }
        )

    sample_too_small = job_count < MIN_JOBS_FOR_RELIABLE_STATS
    note = None
    if sample_too_small:
        note = (
            f'Sample size is small (n={job_count} < {MIN_JOBS_FOR_RELIABLE_STATS}); '
            'percentages are indicative only and should not be treated as market-wide stats.'
        )

    return {
        'job_count': job_count,
        'sample_too_small': sample_too_small,
        'top_skills': top_skills,
        'note': note,
    }


def run_market_trends_agent(state: CareerGraphState, db: Session | None = None) -> dict[str, Any]:
    del db  # reserved for future DB-backed enrichment
    ranked = state.get('ranked_jobs') or []
    logger.info('market_trends_agent start jobs=%s', len(ranked))

    warnings = list(state.get('warnings') or [])
    trends = analyze_market_trends(ranked)
    if trends.get('sample_too_small'):
        warnings.append(f"market_trends_agent: {trends.get('note')}")

    update = append_node_log(
        state,
        'market_trends_agent',
        {
            'event': 'completed',
            'input': {'ranked_job_count': len(ranked)},
            'output_keys': ['market_trends'],
            'top_skill_count': len(trends.get('top_skills') or []),
        },
    )
    update.update(
        {
            'market_trends': trends,
            'warnings': warnings,
            'status': 'running',
        }
    )
    logger.info(
        'market_trends_agent end top_skills=%s sample_too_small=%s',
        len(trends.get('top_skills') or []),
        trends.get('sample_too_small'),
    )
    return update


def make_market_trends_agent_node(
    db: Session | None = None,
) -> Callable[[CareerGraphState], dict[str, Any]]:
    def market_trends_agent_node(state: CareerGraphState) -> dict[str, Any]:
        return run_market_trends_agent(state, db)

    return market_trends_agent_node
