from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


ContentType = Literal['jobs', 'resources', 'cvs']


class RetrievedItem(BaseModel):
    """One retrieved context chunk with provenance for RAG grounding."""

    id: str
    source: ContentType
    score: float
    title: Optional[str] = None
    text: str
    doc_id: Optional[str] = None
    chunk_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    query: str
    top_k: int
    sources: list[ContentType]
    items: list[RetrievedItem]
    latency_ms: float
    empty: bool = False
