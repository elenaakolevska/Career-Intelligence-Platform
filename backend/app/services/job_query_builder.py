"""Build Adzuna query params from a structured CV profile."""

from __future__ import annotations

import re
from typing import Any

# Locations that are unlikely to match Adzuna's configured country market.
_NON_UK_MARKERS = (
    'macedonia',
    'skopje',
    'ohrid',
    'serbia',
    'croatia',
    'bulgaria',
    'albania',
    'kosovo',
    'germany',
    'berlin',
    'france',
    'paris',
    'spain',
    'italy',
    'usa',
    'united states',
    'canada',
    'india',
    'australia',
)

_JOB_TITLE_HINTS = (
    'engineer',
    'developer',
    'programmer',
    'architect',
    'analyst',
    'scientist',
    'intern',
    'consultant',
    'manager',
    'lead',
    'specialist',
)


def _looks_like_job_title(title: str) -> bool:
    lower = title.lower()
    if 'project' in lower:
        return False
    return any(hint in lower for hint in _JOB_TITLE_HINTS)


def _where_for_market(location: str, *, country: str = 'gb') -> str:
    """Drop CV locations that won't match the Adzuna country market (e.g. MK vs GB)."""
    loc = (location or '').strip()
    if not loc:
        return ''
    lower = loc.lower()
    country = (country or 'gb').lower()
    if country in {'gb', 'uk'}:
        if any(marker in lower for marker in _NON_UK_MARKERS):
            return ''
        # Keep UK-ish locations; otherwise omit rather than over-filter
        uk_markers = ('uk', 'united kingdom', 'london', 'manchester', 'england', 'scotland', 'wales', 'remote')
        if any(m in lower for m in uk_markers):
            return loc
        # Unknown / free-text: omit so search is country-wide
        if re.search(r'[^\x00-\x7f]', loc):
            return ''
        return ''
    return loc


def build_job_query(
    structured: dict[str, Any] | None,
    *,
    max_skills: int = 5,
    country: str | None = None,
) -> dict[str, str]:
    from app.core.config import settings

    structured = structured or {}
    skills = [str(s).strip() for s in (structured.get('skills') or []) if str(s).strip()]
    # Prefer hard/tech skills for search keywords (skip soft-skill phrases)
    tech_skills = [s for s in skills if len(s) <= 40 and '&' not in s and s.count(' ') <= 1]
    if not tech_skills:
        tech_skills = skills

    job_titles: list[str] = []
    for exp in structured.get('experience') or []:
        title = (exp or {}).get('title')
        if title and _looks_like_job_title(str(title)):
            job_titles.append(str(title).strip())

    keywords: list[str] = []
    # Skills-first: student CVs often list projects as "experience" titles
    keywords.extend(tech_skills[:max_skills])
    if job_titles:
        keywords.insert(0, job_titles[0])
    elif structured.get('education') and not job_titles:
        # Early-career bias when no real job titles are present
        keywords.insert(0, 'junior graduate software developer')

    if not keywords:
        keywords = ['software engineer']

    what = ' '.join(dict.fromkeys(keywords))  # de-dupe, preserve order
    market = country if country is not None else settings.adzuna_country
    where = _where_for_market(str(structured.get('location') or ''), country=market or 'gb')
    return {
        'what': what,
        'where': where,
    }
