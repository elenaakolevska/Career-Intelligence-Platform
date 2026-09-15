"""RAG pipeline: query → retrieve → build grounded prompt → generate.

P5-02 / P5-04: context is separated from the question; empty retrieval forces
an explicit hedge instead of a confident hallucinated answer.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Sequence

from sqlalchemy.orm import Session

from app import models
from app.clients.llm_client import LLMClient, StubClient, get_llm_client
from app.core.config import settings
from app.schemas.rag import RagResponse, RagTask
from app.schemas.retrieval import ContentType, RetrievedItem
from app.services.cv_service import CVService
from app.services.prompt_loader import NO_CONTEXT_MARKERS, RAG_PROMPT_FILES, render_rag_prompt
from app.services.retrieval_service import RetrievalService

logger = logging.getLogger(__name__)

DEFAULT_SOURCES: dict[RagTask, list[ContentType]] = {
    'market_trends': ['jobs'],
    'skill_gap': ['jobs'],
    'learning_roadmap': ['jobs', 'resources'],
    'gap_narrative': ['jobs', 'resources'],
}

TASK_NO_CONTEXT: dict[RagTask, str] = {
    'market_trends': NO_CONTEXT_MARKERS[0],
    'skill_gap': NO_CONTEXT_MARKERS[1],
    'learning_roadmap': NO_CONTEXT_MARKERS[2],
    'gap_narrative': NO_CONTEXT_MARKERS[3],
}

_CITATION_RE = re.compile(r'\[(jobs|resources|cvs):([^\]]+)\]')


def extract_citations(text: str) -> list[str]:
    """Return deduped ``source:id`` refs cited in a generated answer."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for match in _CITATION_RE.finditer(text):
        ref = f'{match.group(1)}:{match.group(2)}'
        if ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def format_context(items: Sequence[RetrievedItem]) -> str:
    if not items:
        return ''
    blocks: list[str] = []
    for item in items:
        header = f'[{item.source}:{item.id}] score={item.score:.4f}'
        if item.title:
            header += f' title={item.title}'
        meta_bits = []
        for key in ('url', 'company', 'location', 'type', 'skills'):
            if key in item.metadata and item.metadata[key]:
                meta_bits.append(f'{key}={item.metadata[key]}')
        if meta_bits:
            header += ' | ' + '; '.join(meta_bits)
        blocks.append(f'{header}\n{item.text}')
    return '\n\n---\n\n'.join(blocks)


def profile_from_cv(cv: models.CVProfile) -> str:
    structured = CVService.structured_as_dict(cv) or {}
    parts: list[str] = []
    if structured.get('name'):
        parts.append(f"Name: {structured['name']}")
    if structured.get('summary') or cv.summary:
        parts.append(f"Summary: {structured.get('summary') or cv.summary}")
    skills = structured.get('skills') or []
    if skills:
        parts.append('Skills: ' + ', '.join(skills))
    for exp in structured.get('experience') or []:
        bits = [exp.get('title'), exp.get('company'), exp.get('description')]
        parts.append('Experience: ' + ' | '.join(str(b) for b in bits if b))
    if not parts and cv.raw_text:
        parts.append(cv.raw_text[:2000])
    return '\n'.join(parts) if parts else 'No profile data available.'


def _stub_grounded_answer(task: RagTask, context: str, profile: str, question: str) -> str:
    """Deterministic offline generator that stays faithful to retrieved context."""
    if not context.strip():
        return TASK_NO_CONTEXT[task]

    # Pull a few cited lines so answers demonstrably reference retrieval
    citations = []
    for line in context.splitlines():
        if line.startswith('[') and ']' in line:
            citations.append(line.split(']')[0] + ']')
        if len(citations) >= 3:
            break
    cite_str = ', '.join(citations) if citations else '[context]'

    if task == 'market_trends':
        return (
            f'Observed in context: retrieved postings emphasize skills present in {cite_str}. '
            f'Question was: {question}. Profile considered: {profile[:120]}...'
        )
    if task == 'skill_gap':
        return (
            f'Based only on CONTEXT {cite_str}, prioritize gaps relative to PROFILE. '
            f'Question: {question}.'
        )
    if task == 'gap_narrative':
        return (
            f'Grounded in CONTEXT {cite_str}: this gap is evidenced by the retrieved '
            f'postings/resources, which also point to a learning direction. '
            f'Question: {question}.'
        )
    return (
        f'30/60/90 roadmap grounded in CONTEXT resources/jobs {cite_str}. '
        f'Only recommend items appearing in CONTEXT. Question: {question}.'
    )


class RagPipeline:
    def __init__(
        self,
        db: Session | None = None,
        *,
        retrieval: RetrievalService | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        self.db = db
        self.retrieval = retrieval or RetrievalService(db)
        self.llm = llm or get_llm_client()

    def run(
        self,
        query: str,
        *,
        task: RagTask = 'skill_gap',
        profile: str | None = None,
        top_k: int | None = None,
        sources: Sequence[ContentType] | None = None,
        cv_id: int | None = None,
        include_prompt_preview: bool = False,
    ) -> RagResponse:
        started = time.perf_counter()
        if task not in RAG_PROMPT_FILES:
            raise ValueError(f'Unsupported RAG task: {task}')

        resolved_profile = profile or ''
        if not resolved_profile and cv_id is not None and self.db is not None:
            cv = self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
            if cv is not None:
                resolved_profile = profile_from_cv(cv)

        selected_sources = list(sources) if sources else DEFAULT_SOURCES[task]
        retrieval = self.retrieval.retrieve(
            query,
            top_k=top_k or settings.retrieval_top_k,
            sources=selected_sources,
        )
        context_text = format_context(retrieval.items)
        empty_context = retrieval.empty or not context_text.strip()

        prompt = render_rag_prompt(
            task,
            context=context_text if not empty_context else '',
            profile=resolved_profile or 'No profile provided.',
            question=query,
        )

        # P5-02: confirm retrieved context lands in the prompt (when present)
        if not empty_context:
            sample_id = retrieval.items[0].id
            if sample_id not in prompt:
                logger.warning('Retrieved id %s missing from rendered prompt', sample_id)
            else:
                logger.info('RAG prompt includes retrieved context id=%s task=%s', sample_id, task)
        else:
            logger.info('RAG empty context for task=%s; forcing grounded hedge', task)

        gen_started = time.perf_counter()
        if empty_context:
            # Hard guardrail: never ask the LLM to invent when retrieval failed
            answer = TASK_NO_CONTEXT[task]
            grounded = True
        elif isinstance(self.llm, StubClient) or (settings.llm_provider or '').lower() == 'stub':
            answer = _stub_grounded_answer(task, context_text, resolved_profile, query)
            grounded = True
        else:
            answer = self.llm.generate(prompt, max_tokens=1024)
            # Soft check: if model ignored hedge instructions on thin context, normalize
            grounded = True
            if not retrieval.items and TASK_NO_CONTEXT[task] not in answer:
                answer = TASK_NO_CONTEXT[task]

        generation_latency_ms = (time.perf_counter() - gen_started) * 1000
        total_latency_ms = (time.perf_counter() - started) * 1000

        return RagResponse(
            task=task,
            query=query,
            answer=answer,
            grounded=grounded,
            empty_context=empty_context,
            prompt_preview=prompt[:1500] if include_prompt_preview else None,
            retrieval_latency_ms=retrieval.latency_ms,
            generation_latency_ms=generation_latency_ms,
            total_latency_ms=total_latency_ms,
            context_items=list(retrieval.items),
            metadata={'sources': selected_sources, 'cv_id': cv_id},
        )
