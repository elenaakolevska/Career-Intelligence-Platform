"""Retrieval Agent (P6-10): LangGraph node wrapping retrieval + optional RAG.

Other agents enqueue work via ``retrieval_requests`` (or this node derives
queries from ``skill_gaps`` / ``cv_summary``). Results land in
``retrieval_context`` with provenance: query, requesting_agent, source, id.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.agents.state import CareerGraphState, append_node_log
from app.core.config import settings
from app.services.rag_pipeline import RagPipeline, extract_citations
from app.services.retrieval_service import RetrievalService, ensure_resource_index

logger = logging.getLogger(__name__)


def build_retrieval_requests(state: CareerGraphState) -> list[dict[str, Any]]:
    """Build retrieval requests from explicit queue or upstream skill gaps."""
    existing = list(state.get('retrieval_requests') or [])  # type: ignore[arg-type]
    if existing:
        return existing

    requests: list[dict[str, Any]] = []
    gaps = state.get('skill_gaps') or []
    for gap in gaps[:8]:
        skill = str((gap or {}).get('skill') or '').strip()
        if not skill:
            continue
        requests.append(
            {
                'query': f'{skill} learning course tutorial book',
                'requesting_agent': 'skill_gap_agent',
                'sources': ['resources'],
                'top_k': 3,
                'skill': skill,
            }
        )

    summary = (state.get('cv_summary') or '').strip()
    if summary:
        requests.append(
            {
                'query': summary[:400],
                'requesting_agent': 'cv_agent',
                'sources': ['jobs', 'resources'],
                'top_k': settings.retrieval_top_k,
                'skill': None,
            }
        )

    if not requests:
        requests.append(
            {
                'query': 'software engineering career skills',
                'requesting_agent': 'retrieval_agent',
                'sources': ['resources'],
                'top_k': 5,
                'skill': None,
            }
        )
    return requests


def run_retrieval_agent(
    state: CareerGraphState,
    db: Session | None = None,
) -> dict[str, Any]:
    logger.info('retrieval_agent start')
    warnings = list(state.get('warnings') or [])
    retrieval = RetrievalService(db)
    ensure_resource_index(store=retrieval.resources_store)

    requests = build_retrieval_requests(state)
    context_items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for req in requests:
        query = str(req.get('query') or '').strip()
        if not query:
            continue
        requesting_agent = str(req.get('requesting_agent') or 'unknown')
        sources = req.get('sources') or ['resources']
        top_k = int(req.get('top_k') or settings.retrieval_top_k)
        result = retrieval.retrieve(query, top_k=top_k, sources=sources)  # type: ignore[arg-type]

        for item in result.items:
            key = (item.source, item.id)
            if key in seen:
                continue
            seen.add(key)
            context_items.append(
                {
                    'id': item.id,
                    'source': item.source,
                    'score': item.score,
                    'title': item.title,
                    'text': item.text,
                    'url': (item.metadata or {}).get('url'),
                    'type': (item.metadata or {}).get('type'),
                    'metadata': item.metadata or {},
                    'query': query,
                    'requesting_agent': requesting_agent,
                    'skill': req.get('skill'),
                }
            )

    if not context_items:
        warnings.append('retrieval_agent: no context retrieved for queued queries')

    # Grounded narratives for the top 3 gaps (deterministic gaps remain the
    # source of truth; RAG only explains relevance / evidence / learning direction).
    narratives, sources = _run_gap_narratives(state, retrieval, db)

    # Preserve any prior context, then append fresh results
    prior = list(state.get('retrieval_context') or [])
    update = append_node_log(
        state,
        'retrieval_agent',
        {
            'event': 'completed',
            'input': {'request_count': len(requests)},
            'output_keys': ['retrieval_context', 'retrieval_narratives', 'sources'],
            'context_count': len(context_items),
            'narrative_count': len(narratives),
            'queries': [r.get('query') for r in requests],
        },
    )
    update.update(
        {
            'retrieval_context': prior + context_items,
            'retrieval_requests': [],  # clear queue after processing
            'retrieval_narratives': narratives,
            'sources': sources,
            'warnings': warnings,
            'status': 'running',
        }
    )
    logger.info(
        'retrieval_agent end context=%s requests=%s narratives=%s',
        len(context_items),
        len(requests),
        len(narratives),
    )
    return update


def _run_gap_narratives(
    state: CareerGraphState,
    retrieval: RetrievalService,
    db: Session | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate RAG-grounded narratives for the top 3 skill gaps.

    Returns (narratives, sources). Each narrative explains why the gap is
    relevant and cites retrieved evidence; the deterministic skill_gaps list
    remains authoritative for what the gaps actually are.
    """
    gaps = list(state.get('skill_gaps') or [])
    profile = state.get('cv_summary') or ''
    narratives: list[dict[str, Any]] = []
    sources_by_ref: dict[str, dict[str, Any]] = {}

    for gap in gaps[:3]:
        skill = str((gap or {}).get('skill') or '').strip()
        if not skill:
            continue
        query = f'{skill}: why it matters and how to learn it'
        try:
            rag = RagPipeline(db, retrieval=retrieval)
            result = rag.run(
                query,
                task='gap_narrative',
                profile=profile,
                top_k=3,
                sources=['jobs', 'resources'],
            )
        except Exception as exc:  # noqa: BLE001 — keep narrative optional
            logger.warning('gap_narrative RAG failed for %r: %s', skill, exc)
            continue

        context_items = [
            {
                'id': item.id,
                'source': item.source,
                'doc_id': item.doc_id,
                'chunk_id': item.chunk_id,
                'score': item.score,
                'title': item.title,
                'url': (item.metadata or {}).get('url'),
            }
            for item in result.context_items
        ]

        citations = extract_citations(result.answer)
        for item in context_items:
            ref = f"{item['source']}:{item['doc_id'] or item['id']}"
            if ref in sources_by_ref:
                continue
            sources_by_ref[ref] = {
                'ref': ref,
                'source': item['source'],
                'title': item['title'],
                'url': item['url'],
            }

        narratives.append(
            {
                'skill': skill,
                'priority': (gap or {}).get('priority'),
                'task': 'gap_narrative',
                'answer': result.answer,
                'grounded': result.grounded,
                'empty_context': result.empty_context,
                'citations': citations,
                'context_items': context_items,
            }
        )

    return narratives, list(sources_by_ref.values())


def make_retrieval_agent_node(
    db: Session | None = None,
) -> Callable[[CareerGraphState], dict[str, Any]]:
    def retrieval_agent_node(state: CareerGraphState) -> dict[str, Any]:
        return run_retrieval_agent(state, db)

    return retrieval_agent_node
