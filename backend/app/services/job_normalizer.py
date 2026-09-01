"""Normalize Adzuna (or mock) job payloads into JobPosting fields."""

from __future__ import annotations

from typing import Any


def normalize_adzuna_job(item: dict[str, Any], *, source: str = 'adzuna') -> dict[str, Any]:
    salary_min = item.get('salary_min')
    salary_max = item.get('salary_max')
    company = item.get('company') or {}
    if isinstance(company, dict):
        company_name = company.get('display_name')
    else:
        company_name = str(company) if company else None

    location = item.get('location') or {}
    if isinstance(location, dict):
        location_name = location.get('display_name')
    else:
        location_name = str(location) if location else None

    salary_raw = None
    if salary_min is not None or salary_max is not None:
        salary_raw = f'{salary_min or ""}-{salary_max or ""}'.strip('-')

    external_id = str(item.get('id') or item.get('external_id') or '')
    return {
        'title': str(item.get('title') or 'Untitled'),
        'company': company_name,
        'location': location_name,
        'description': item.get('description'),
        'url': item.get('redirect_url') or item.get('url'),
        'salary_min': float(salary_min) if salary_min is not None else None,
        'salary_max': float(salary_max) if salary_max is not None else None,
        'salary_raw': salary_raw,
        'external_id': external_id or None,
        'source': source,
    }
