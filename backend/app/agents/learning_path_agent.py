"""Learning Path Agent (P6-06): 30/60/90 roadmap from skill gaps + retrieved resources."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable
from urllib.parse import quote_plus

from sqlalchemy.orm import Session

from app.agents.skill_utils import canonicalize_skill, normalize_skill_key
from app.agents.state import CareerGraphState, append_node_log
from app.clients.learning_resources import OpenLibraryClient, SerpAPIClient
from app.core.exceptions import ExternalServiceError
from app.data.mock_resources import MOCK_RESOURCES
from app.schemas.retrieval import RetrievedItem
from app.services.retrieval_service import RetrievalService, ensure_resource_index

logger = logging.getLogger(__name__)

ROADMAP_SECTION_KEYS = ('days_30', 'days_60', 'days_90')


def _skill_keys(skill: str) -> set[str]:
    """Normalized keys used to match a skill against resource tags / text."""
    raw = (skill or '').strip()
    canon = canonicalize_skill(raw)
    keys = {normalize_skill_key(raw), normalize_skill_key(canon)}
    keys.discard('')
    # Also keep a compact form without spaces (ci/cd → cicd)
    for k in list(keys):
        keys.add(re.sub(r'[\s/&.]+', '', k))
    return keys


def _tags_match_skill(skill: str, tags: list[str]) -> bool:
    skill_keys = _skill_keys(skill)
    tag_keys = {normalize_skill_key(t) for t in tags if t}
    tag_keys |= {re.sub(r'[\s/&.]+', '', t) for t in tag_keys}
    if skill_keys & tag_keys:
        return True
    # Substring only for longer tokens (avoid "c" / "go" false positives)
    for sk in skill_keys:
        if len(sk) < 3:
            continue
        for tk in tag_keys:
            if len(tk) < 3:
                continue
            if sk in tk or tk in sk:
                return True
    return False


def _resource_from_retrieved(item: RetrievedItem, skill: str) -> dict[str, Any] | None:
    url = item.metadata.get('url') if item.metadata else None
    if not url:
        # Only recommend resources with real URLs (no invented links)
        return None
    return {
        'id': item.id,
        'title': item.title or item.id,
        'url': url,
        'type': (item.metadata or {}).get('type') or 'resource',
        'source': item.source,
        'skill': skill,
        'score': item.score,
    }


def _resource_from_mock(skill: str, *, used_ids: set[str]) -> dict[str, Any] | None:
    """Match against curated corpus by skill tag (real docs / course URLs)."""
    for res in MOCK_RESOURCES:
        if res['id'] in used_ids:
            continue
        tags = [str(s) for s in (res.get('skills') or [])]
        if not _tags_match_skill(skill, tags):
            continue
        url = res.get('url')
        if not url:
            continue
        used_ids.add(res['id'])
        return {
            'id': res['id'],
            'title': res.get('title') or res['id'],
            'url': url,
            'type': res.get('type') or 'resource',
            'source': 'resources',
            'skill': skill,
            'score': 1.0,
        }
    return None


def _resources_from_context(
    skill: str,
    context: list[dict[str, Any]],
    *,
    used_ids: set[str],
) -> list[dict[str, Any]]:
    """Pick learning resources already retrieved by the Retrieval Agent."""
    skill_keys = _skill_keys(skill)
    picked: list[dict[str, Any]] = []
    for item in context:
        item_id = str(item.get('id') or '')
        if not item_id or item_id in used_ids:
            continue
        if item.get('source') not in {'resources', 'resource'} and item.get('type') == 'rag_answer':
            continue
        url = item.get('url') or (item.get('metadata') or {}).get('url')
        if not url:
            continue
        item_skill = str(item.get('skill') or '')
        text_blob = ' '.join(str(item.get(k) or '') for k in ('title', 'text', 'query')).lower()
        matched = _tags_match_skill(skill, [item_skill]) or any(
            k in text_blob for k in skill_keys if len(k) >= 3
        )
        if not matched:
            continue
        used_ids.add(item_id)
        picked.append(
            {
                'id': item_id,
                'title': item.get('title') or item_id,
                'url': url,
                'type': item.get('type') or (item.get('metadata') or {}).get('type') or 'resource',
                'source': item.get('source') or 'resources',
                'skill': skill,
                'score': float(item.get('score') or 0.0),
            }
        )
        if len(picked) >= 2:
            break
    return picked


def _slug_skill(skill: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', normalize_skill_key(skill)).strip('-') or 'skill'


def _external_resources_for_skill(skill: str, *, used_ids: set[str], limit: int = 2) -> list[dict[str, Any]]:
    """Live SerpAPI courses + Open Library books when available; mock Coursera URL otherwise."""
    picked: list[dict[str, Any]] = []
    query = canonicalize_skill(skill) or skill

    try:
        for item in SerpAPIClient(timeout=8).search_courses(query, num=3):
            url = item.get('url')
            if not url:
                continue
            rid = f"serpapi:{_slug_skill(skill)}:{len(picked)}"
            if rid in used_ids:
                continue
            used_ids.add(rid)
            picked.append(
                {
                    'id': rid,
                    'title': item.get('title') or f'{skill} course',
                    'url': url,
                    'type': item.get('type') or 'course',
                    'source': item.get('source') or 'serpapi',
                    'skill': skill,
                    'score': 0.85,
                }
            )
            if len(picked) >= limit:
                return picked
    except (ExternalServiceError, Exception) as exc:
        logger.warning('SerpAPI resources unavailable for %s: %s', skill, exc)

    try:
        for item in OpenLibraryClient(timeout=8).search_books(f'{query} programming', limit=3):
            url = item.get('url')
            if not url:
                continue
            rid = f"openlibrary:{_slug_skill(skill)}:{len(picked)}"
            if rid in used_ids:
                continue
            used_ids.add(rid)
            picked.append(
                {
                    'id': rid,
                    'title': item.get('title') or f'{skill} book',
                    'url': url,
                    'type': item.get('type') or 'book',
                    'source': item.get('source') or 'openlibrary',
                    'skill': skill,
                    'score': 0.75,
                }
            )
            if len(picked) >= limit:
                break
    except (ExternalServiceError, Exception) as exc:
        logger.warning('Open Library resources unavailable for %s: %s', skill, exc)

    return picked


def _search_fallback_resources(skill: str, *, used_ids: set[str], limit: int = 2) -> list[dict[str, Any]]:
    """Always-on search pages so every skill still has a learn link."""
    q = quote_plus(skill)
    slug = _slug_skill(skill)
    candidates = [
        {
            'id': f'search-fcc:{slug}',
            'title': f'{skill} on freeCodeCamp',
            'url': f'https://www.freecodecamp.org/news/search/?query={q}',
            'type': 'course',
            'source': 'search-fallback',
            'skill': skill,
            'score': 0.55,
        },
        {
            'id': f'search-yt:{slug}',
            'title': f'{skill} tutorials on YouTube',
            'url': f'https://www.youtube.com/results?search_query={q}+tutorial',
            'type': 'video',
            'source': 'search-fallback',
            'skill': skill,
            'score': 0.5,
        },
        {
            'id': f'search-coursera:{slug}',
            'title': f'{skill} courses on Coursera',
            'url': f'https://www.coursera.org/search?query={q}',
            'type': 'course',
            'source': 'search-fallback',
            'skill': skill,
            'score': 0.5,
        },
    ]
    picked: list[dict[str, Any]] = []
    for item in candidates:
        if item['id'] in used_ids:
            continue
        used_ids.add(item['id'])
        picked.append(item)
        if len(picked) >= limit:
            break
    return picked


def _retrieve_resources_for_skill(
    skill: str,
    retrieval: RetrievalService,
    *,
    used_ids: set[str],
    top_k: int = 3,
    retrieval_context: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    skill_keys = _skill_keys(skill)

    # 1) Curated corpus first (best quality, deterministic URLs)
    exact = _resource_from_mock(skill, used_ids=used_ids)
    if exact:
        picked.append(exact)

    # 2) Retrieval Agent context when skill is clearly evidenced
    if retrieval_context and len(picked) < 2:
        for item in _resources_from_context(skill, retrieval_context, used_ids=used_ids):
            title_l = str(item.get('title') or '').lower()
            if any(k in title_l for k in skill_keys if len(k) >= 2) or _tags_match_skill(
                skill, [str(item.get('skill') or '')]
            ):
                picked.append(item)
            if len(picked) >= 2:
                break

    # 3) FAISS / retrieval service
    if len(picked) < 2:
        result = retrieval.retrieve(
            f'{skill} learning course tutorial book',
            top_k=top_k,
            sources=['resources'],
        )
        for item in result.items:
            if item.id in used_ids:
                continue
            blob = f'{item.title or ""} {item.text or ""} {(item.id or "")}'.lower()
            meta_skills = [str(s) for s in ((item.metadata or {}).get('skills') or [])]
            if not (_tags_match_skill(skill, meta_skills) or any(k in blob for k in skill_keys if len(k) >= 3)):
                continue
            resource = _resource_from_retrieved(item, skill)
            if resource is None:
                continue
            used_ids.add(item.id)
            picked.append(resource)
            if len(picked) >= 2:
                break

    # 4) Live APIs when curated/FAISS found nothing
    if not picked:
        picked.extend(_external_resources_for_skill(skill, used_ids=used_ids, limit=2))

    # 5) Guaranteed search-page fallbacks so no skill is left without a link
    if not picked:
        picked.extend(_search_fallback_resources(skill, used_ids=used_ids, limit=2))

    return picked


def _split_gaps_into_horizons(gaps: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Assign gaps to 30/60/90 by priority; single-gap CVs still get three phases."""
    if not gaps:
        return {'days_30': [], 'days_60': [], 'days_90': []}

    # One gap → same skill across horizons with distinct focus (handled by focus_labels)
    if len(gaps) == 1:
        g = gaps[0]
        return {'days_30': [g], 'days_60': [g], 'days_90': [g]}

    high = [g for g in gaps if g.get('priority') == 'high']
    medium = [g for g in gaps if g.get('priority') == 'medium']
    low = [g for g in gaps if g.get('priority') == 'low']
    other = [g for g in gaps if g.get('priority') not in {'high', 'medium', 'low'}]

    days_30 = list(high) or list(medium[:1]) or list(gaps[:1])
    remaining = [g for g in gaps if g not in days_30]
    days_60 = list(medium) if medium else remaining[: max(1, len(remaining) // 2)]
    days_60 = [g for g in days_60 if g not in days_30] or list(remaining[:1])
    used = {id(g) for g in days_30 + days_60}
    days_90 = [g for g in (low + other + remaining) if id(g) not in used]
    if not days_90 and remaining:
        days_90 = [remaining[-1]]
    if not days_90 and gaps:
        days_90 = [gaps[-1]]

    def uniq(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for item in items:
            name = str(item.get('skill') or '')
            if name and name not in seen:
                seen.add(name)
                out.append(item)
        return out

    return {
        'days_30': uniq(days_30),
        'days_60': uniq(days_60),
        'days_90': uniq(days_90),
    }


def build_learning_roadmap(
    skill_gaps: list[dict[str, Any]] | None,
    *,
    retrieval: RetrievalService | None = None,
    profile_summary: str | None = None,
    retrieval_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    gaps = list(skill_gaps or [])
    retrieval = retrieval or RetrievalService()
    ensure_resource_index(store=retrieval.resources_store)

    if not gaps:
        return {
            'days_30': {'focus': 'No critical gaps identified', 'skills': [], 'resources': []},
            'days_60': {'focus': 'No intermediate gaps identified', 'skills': [], 'resources': []},
            'days_90': {'focus': 'No advanced gaps identified', 'skills': [], 'resources': []},
            'notes': 'No skill gaps available; roadmap left empty rather than inventing content.',
            'profile_excerpt': (profile_summary or '')[:200] or None,
        }

    horizons = _split_gaps_into_horizons(gaps)
    used_ids: set[str] = set()
    sections: dict[str, Any] = {}
    focus_labels = {
        'days_30': 'Critical foundations (first 30 days)',
        'days_60': 'Applied practice & infrastructure (30–60 days)',
        'days_90': 'Advanced topics & interview readiness (60–90 days)',
    }

    for key in ROADMAP_SECTION_KEYS:
        section_gaps = horizons[key]
        skills = [str(g['skill']) for g in section_gaps if g.get('skill')]
        resources: list[dict[str, Any]] = []
        # One resource per skill per horizon keeps 30/60/90 distinct for thin gap lists
        per_skill_limit = 2 if key == 'days_30' else 1
        for skill in skills:
            found = _retrieve_resources_for_skill(
                skill,
                retrieval,
                used_ids=used_ids,
                top_k=3,
                retrieval_context=retrieval_context,
            )
            resources.extend(found[:per_skill_limit])
        sections[key] = {
            'focus': focus_labels[key],
            'skills': skills,
            'resources': resources,
            'gap_details': [
                {
                    'skill': g.get('skill'),
                    'priority': g.get('priority'),
                    'demand_pct': g.get('demand_pct'),
                }
                for g in section_gaps
            ],
        }

    return {
        **sections,
        'notes': 'Resources prefer curated docs, then live search APIs, then search-page fallbacks.',
        'profile_excerpt': (profile_summary or '')[:200] or None,
    }


def run_learning_path_agent(state: CareerGraphState, db: Session | None = None) -> dict[str, Any]:
    gaps = state.get('skill_gaps') or []
    summary = state.get('cv_summary')
    logger.info('learning_path_agent start gaps=%s', len(gaps))

    warnings = list(state.get('warnings') or [])
    retrieval = RetrievalService(db)
    context = list(state.get('retrieval_context') or [])
    roadmap = build_learning_roadmap(
        gaps,
        retrieval=retrieval,
        profile_summary=summary,
        retrieval_context=context or None,
    )

    if not gaps:
        warnings.append('learning_path_agent: no skill_gaps; empty roadmap')
    elif not any(roadmap[k]['resources'] for k in ROADMAP_SECTION_KEYS):
        warnings.append('learning_path_agent: no retrieved resources matched gaps')

    update = append_node_log(
        state,
        'learning_path_agent',
        {
            'event': 'completed',
            'input': {
                'gap_count': len(gaps),
                'used_retrieval_context': bool(context),
            },
            'output_keys': ['learning_roadmap'],
            'sections': {
                k: {
                    'skills': roadmap[k]['skills'],
                    'resource_count': len(roadmap[k]['resources']),
                }
                for k in ROADMAP_SECTION_KEYS
            },
        },
    )
    update.update(
        {
            'learning_roadmap': roadmap,
            'warnings': warnings,
            'status': 'running',
        }
    )
    logger.info('learning_path_agent end')
    return update


def make_learning_path_agent_node(
    db: Session | None = None,
) -> Callable[[CareerGraphState], dict[str, Any]]:
    def learning_path_agent_node(state: CareerGraphState) -> dict[str, Any]:
        return run_learning_path_agent(state, db)

    return learning_path_agent_node
