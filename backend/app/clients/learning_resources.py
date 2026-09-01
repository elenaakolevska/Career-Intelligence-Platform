"""SerpAPI + Open Library learning resource clients."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

_STOP = frozenset(
    {
        'a',
        'an',
        'the',
        'and',
        'or',
        'of',
        'to',
        'in',
        'on',
        'for',
        'with',
        'book',
        'guide',
        'learn',
        'learning',
        'course',
        'tutorial',
    }
)


def normalize_resource(
    *,
    title: str,
    url: str | None,
    resource_type: str,
    source: str,
    description: str | None = None,
) -> dict[str, Any]:
    return {
        'title': title,
        'url': url,
        'type': resource_type,
        'source': source,
        'description': description,
    }


def _tokens(text: str) -> set[str]:
    return {
        w
        for w in re.findall(r'[a-z0-9]+', (text or '').lower())
        if len(w) > 2 and w not in _STOP
    }


def _title_matches_query(title: str, query: str, *, min_overlap: float = 0.34) -> bool:
    """Reject Open Library hits whose title is unrelated to the search topic."""
    qt = _tokens(query)
    tt = _tokens(title)
    if not qt or not tt:
        return False
    # At least one strong query token must appear in the title, and Jaccard-ish overlap
    if not (qt & tt):
        return False
    return len(qt & tt) / len(qt) >= min_overlap


class SerpAPIClient:
    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = api_key if api_key is not None else settings.serpapi_api_key
        self._client = httpx.Client(timeout=timeout)

    def search_courses(self, skill: str, *, num: int = 5) -> list[dict[str, Any]]:
        if not self.api_key:
            # Graceful offline fallback
            return [
                normalize_resource(
                    title=f'{skill} course (mock)',
                    url=f'https://www.coursera.org/search?query={skill}',
                    resource_type='course',
                    source='serpapi-mock',
                )
            ]
        try:
            response = self._client.get(
                'https://serpapi.com/search.json',
                params={'engine': 'google', 'q': f'{skill} online course', 'api_key': self.api_key, 'num': num},
            )
            response.raise_for_status()
            organic = response.json().get('organic_results') or []
            return [
                normalize_resource(
                    title=item.get('title') or skill,
                    url=item.get('link'),
                    resource_type='course',
                    source='serpapi',
                    description=item.get('snippet'),
                )
                for item in organic[:num]
            ]
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f'SerpAPI request failed: {exc}') from exc


class OpenLibraryClient:
    def __init__(self, timeout: int = 30) -> None:
        self._client = httpx.Client(timeout=timeout)

    def search_books(self, topic: str, *, limit: int = 5) -> list[dict[str, Any]]:
        topic = (topic or '').strip()
        if not topic:
            return []
        try:
            # Prefer title search so we don't get random music albums for tech topics
            response = self._client.get(
                'https://openlibrary.org/search.json',
                params={
                    'title': topic,
                    'q': f'{topic} programming computer software',
                    'limit': max(limit * 4, 12),
                    'language': 'eng',
                },
            )
            response.raise_for_status()
            docs = response.json().get('docs') or []
            results: list[dict[str, Any]] = []
            seen: set[str] = set()
            for doc in docs:
                title = str(doc.get('title') or '').strip()
                key = doc.get('key')
                if not title or not key or key in seen:
                    continue
                if not _title_matches_query(title, topic):
                    continue
                seen.add(key)
                slug = re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_') or 'book'
                url = f'https://openlibrary.org{key}/{slug}'
                results.append(
                    normalize_resource(
                        title=title,
                        url=url,
                        resource_type='book',
                        source='openlibrary',
                        description=', '.join(doc.get('author_name') or []) or None,
                    )
                )
                if len(results) >= limit:
                    break
            return results
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f'Open Library request failed: {exc}') from exc
