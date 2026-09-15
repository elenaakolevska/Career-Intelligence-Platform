"""RAG retrieval service: query → embed → multi-source FAISS → grounded context.

Supports multiple content types through a shared interface so the future
Retrieval Agent (P6-10) can request jobs, learning resources, or both.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from app import models
from app.core.config import settings
from app.data.mock_resources import MOCK_RESOURCES
from app.schemas.retrieval import ContentType, RetrievedItem, RetrievalResult
from app.services.chunker import chunk_text
from app.services.embedding_service import build_job_embedding_text, embed
from app.services.faiss_store import FaissStore, get_store

logger = logging.getLogger(__name__)

SUPPORTED_SOURCES: tuple[ContentType, ...] = ('jobs', 'resources')


def _bounded_top_k(top_k: int | None) -> int:
    default = getattr(settings, 'retrieval_top_k', None) or settings.similarity_top_k
    k = default if top_k is None else int(top_k)
    return max(1, min(k, 50))


def _normalize_sources(sources: Sequence[ContentType] | None) -> list[ContentType]:
    if not sources:
        return list(SUPPORTED_SOURCES)
    normalized: list[ContentType] = []
    for source in sources:
        name = str(source).strip().lower()  # type: ignore[arg-type]
        if name in SUPPORTED_SOURCES and name not in normalized:
            normalized.append(name)  # type: ignore[arg-type]
    return normalized or list(SUPPORTED_SOURCES)


def _resource_body(resource: dict) -> str:
    return (resource.get('description') or resource.get('title') or '').strip()


def _resource_chunk_embedding_text(resource: dict, chunk: str) -> str:
    skills = ', '.join(resource.get('skills') or [])
    parts = [
        resource.get('title') or '',
        chunk,
        f'Skills: {skills}' if skills else '',
        resource.get('type') or '',
    ]
    return '\n'.join(p for p in parts if p)


@lru_cache(maxsize=1)
def _resource_chunk_index() -> dict[str, dict]:
    """Map chunk_id -> metadata for every chunk of MOCK_RESOURCES."""
    out: dict[str, dict] = {}
    for item in MOCK_RESOURCES:
        doc_id = str(item['id'])
        chunks = chunk_text(_resource_body(item))
        if not chunks:
            chunks = ['']
        for idx, chunk in enumerate(chunks):
            cid = f'{doc_id}#{idx}'
            out[cid] = {
                'doc_id': doc_id,
                'chunk_id': cid,
                'chunk_index': idx,
                'title': item.get('title'),
                'url': item.get('url'),
                'type': item.get('type'),
                'skills': item.get('skills') or [],
                'text': chunk,
            }
    return out


def index_resources(
    resources: Iterable[dict] | None = None,
    *,
    store: FaissStore | None = None,
) -> int:
    """Embed and upsert chunked learning resources into the resources FAISS index."""
    corpus = list(resources) if resources is not None else list(MOCK_RESOURCES)
    if not corpus:
        return 0
    target = store or get_store('resources')

    batch: list[tuple[str, str]] = []
    for item in corpus:
        doc_id = str(item['id'])
        chunks = chunk_text(_resource_body(item))
        if not chunks:
            chunks = ['']
        for idx, chunk in enumerate(chunks):
            batch.append((f'{doc_id}#{idx}', _resource_chunk_embedding_text(item, chunk)))

    vectors = embed([text for _, text in batch])
    for (chunk_id, _text), vector in zip(batch, vectors):
        target.add(chunk_id, vector)
    return len(batch)


def ensure_resource_index(*, store: FaissStore | None = None) -> FaissStore:
    target = store or get_store('resources')
    expected = set(_resource_chunk_index().keys())
    if set(target._ids) == expected:
        return target
    # Corpus changed or index is legacy/whole-doc — rebuild cleanly.
    if target.size:
        target.clear()
    index_resources(store=target)
    return target


def _hydrate_job(db: Session | None, entity_id: str, score: float) -> RetrievedItem | None:
    title = None
    text = f'Job posting {entity_id}'
    metadata: dict = {'entity_id': entity_id}
    if db is not None:
        try:
            job_id = int(entity_id)
        except ValueError:
            job_id = None
        job = None
        if job_id is not None:
            job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
        if job is not None:
            title = job.title
            text = build_job_embedding_text(job)
            metadata.update(
                {
                    'job_id': job.id,
                    'company': job.company,
                    'location': job.location,
                    'url': job.url,
                    'external_id': job.external_id,
                    'source_name': job.source,
                }
            )
    return RetrievedItem(
        id=str(entity_id),
        source='jobs',
        score=score,
        title=title,
        text=text,
        doc_id=str(entity_id),
        chunk_id=str(entity_id),
        metadata=metadata,
    )


def _hydrate_resource(entity_id: str, score: float) -> RetrievedItem | None:
    info = _resource_chunk_index().get(entity_id)
    if info is None:
        return RetrievedItem(
            id=str(entity_id),
            source='resources',
            score=score,
            title=None,
            text=f'Learning resource {entity_id}',
            metadata={'entity_id': entity_id},
        )
    return RetrievedItem(
        id=str(entity_id),
        source='resources',
        score=score,
        title=info['title'],
        text=info['text'],
        doc_id=info['doc_id'],
        chunk_id=info['chunk_id'],
        metadata={
            'doc_id': info['doc_id'],
            'chunk_index': info['chunk_index'],
            'url': info['url'],
            'type': info['type'],
            'skills': info['skills'],
        },
    )


class RetrievalService:
    """Shared retrieval interface used by RAG and (later) the Retrieval Agent."""

    def __init__(
        self,
        db: Session | None = None,
        *,
        jobs_store: FaissStore | None = None,
        resources_store: FaissStore | None = None,
    ) -> None:
        self.db = db
        self.jobs_store = jobs_store or get_store('jobs')
        self.resources_store = resources_store or get_store('resources')

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        sources: Sequence[ContentType] | None = None,
    ) -> RetrievalResult:
        started = time.perf_counter()
        q = (query or '').strip()
        k = _bounded_top_k(top_k)
        selected = _normalize_sources(sources)

        if not q:
            latency_ms = (time.perf_counter() - started) * 1000
            return RetrievalResult(
                query=query or '',
                top_k=k,
                sources=selected,
                items=[],
                latency_ms=latency_ms,
                empty=True,
            )

        vector = embed(q)[0]
        per_source_k = k  # fetch k from each source, then merge/trim
        candidates: list[RetrievedItem] = []

        if 'jobs' in selected:
            if self.jobs_store.size == 0 and self.db is not None:
                # Lazy seed from DB jobs if index is empty but rows exist
                jobs = self.db.query(models.JobPosting).limit(100).all()
                if jobs:
                    texts = [build_job_embedding_text(job) for job in jobs]
                    vectors = embed(texts)
                    for job, vec in zip(jobs, vectors):
                        self.jobs_store.add(str(job.id), vec)
            for entity_id, score in self.jobs_store.search(vector, top_k=per_source_k):
                item = _hydrate_job(self.db, entity_id, score)
                if item is not None:
                    candidates.append(item)

        if 'resources' in selected:
            ensure_resource_index(store=self.resources_store)
            for entity_id, score in self.resources_store.search(vector, top_k=per_source_k):
                item = _hydrate_resource(entity_id, score)
                if item is not None:
                    candidates.append(item)

        candidates.sort(key=lambda item: item.score, reverse=True)
        items = candidates[:k]
        latency_ms = (time.perf_counter() - started) * 1000
        logger.info(
            'retrieval query=%r sources=%s hits=%s latency_ms=%.2f',
            q[:80],
            selected,
            len(items),
            latency_ms,
        )
        return RetrievalResult(
            query=q,
            top_k=k,
            sources=selected,
            items=items,
            latency_ms=latency_ms,
            empty=len(items) == 0,
        )
