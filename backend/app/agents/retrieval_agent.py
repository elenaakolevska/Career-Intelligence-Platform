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
from app.schemas.retrieval import ContentType
from app.services.rag_pipeline import RagPipeline
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
    *,
    run_rag: bool = False,
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

        if run_rag:
            rag = RagPipeline(db, retrieval=retrieval)
            rag_result = rag.run(
                query,
                task='learning_roadmap',
                profile=state.get('cv_summary'),
                top_k=top_k,
                sources=sources,  # type: ignore[arg-type]
            )
            context_items.append(
                {
                    'id': f'rag:{requesting_agent}:{len(context_items)}',
                    'source': 'rag',
                    'score': 1.0,
                    'title': 'RAG answer',
                    'text': rag_result.answer,
                    'url': None,
                    'type': 'rag_answer',
                    'metadata': {'empty_context': rag_result.empty_context},
                    'query': query,
                    'requesting_agent': requesting_agent,
                    'skill': req.get('skill'),
                }
            )

    if not context_items:
        warnings.append('retrieval_agent: no context retrieved for queued queries')

    # Preserve any prior context, then append fresh results
    prior = list(state.get('retrieval_context') or [])
    update = append_node_log(
        state,
        'retrieval_agent',
        {
            'event': 'completed',
            'input': {'request_count': len(requests)},
            'output_keys': ['retrieval_context'],
            'context_count': len(context_items),
            'queries': [r.get('query') for r in requests],
        },
    )
    update.update(
        {
            'retrieval_context': prior + context_items,
            'retrieval_requests': [],  # clear queue after processing
            'warnings': warnings,
            'status': 'running',
        }
    )
    logger.info('retrieval_agent end context=%s requests=%s', len(context_items), len(requests))
    return update


def make_retrieval_agent_node(
    db: Session | None = None,
) -> Callable[[CareerGraphState], dict[str, Any]]:
    def retrieval_agent_node(state: CareerGraphState) -> dict[str, Any]:
        return run_retrieval_agent(state, db)

    return retrieval_agent_node
