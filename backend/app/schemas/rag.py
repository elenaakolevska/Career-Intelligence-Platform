from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.retrieval import ContentType, RetrievedItem


RagTask = Literal['market_trends', 'skill_gap', 'learning_roadmap', 'gap_narrative']


class RagRequest(BaseModel):
    query: str
    task: RagTask = 'skill_gap'
    profile: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=50)
    sources: Optional[list[ContentType]] = None
    cv_id: Optional[int] = None


class RagResponse(BaseModel):
    task: RagTask
    query: str
    answer: str
    grounded: bool
    empty_context: bool
    prompt_preview: Optional[str] = None
    retrieval_latency_ms: float
    generation_latency_ms: float
    total_latency_ms: float
    context_items: list[RetrievedItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
