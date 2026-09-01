from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class InterviewTurnSchema(BaseModel):
    turn_index: int
    question: str
    answer: Optional[str] = None
    score: Optional[float] = Field(default=None, ge=0, le=10)
    feedback: Optional[str] = None
    difficulty: Optional[str] = None
    topics: Optional[list[str]] = None
    asked_at: Optional[str] = None
    answered_at: Optional[str] = None


class InterviewCreate(BaseModel):
    role: Optional[str] = None
    cv_id: Optional[int] = None
    difficulty: Optional[str] = 'junior'
    # Deprecated: ignored in favor of JWT subject; kept for older clients
    user_id: Optional[int] = None


class InterviewAnswerCreate(BaseModel):
    """Submit an answer to the current pending interview question (P7-03)."""

    answer: str = Field(..., min_length=1)


class InterviewComplete(BaseModel):
    """Mark a session completed (P7-05)."""

    overall_feedback: Optional[str] = None


class InterviewHistoryRead(BaseModel):
    """Full Q&A history for review after/during a session (P7-05)."""

    session_id: int
    user_id: int
    role: Optional[str] = None
    difficulty: Optional[str] = None
    status: str
    in_progress: bool
    running_score: Optional[float] = None
    overall_feedback: Optional[str] = None
    history: list[InterviewTurnSchema] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InterviewSummary(BaseModel):
    """Lightweight reverse-chronological list item (P7-05)."""

    id: int
    user_id: int
    role: Optional[str] = None
    difficulty: Optional[str] = None
    status: str
    in_progress: bool
    running_score: Optional[float] = None
    turn_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InterviewRead(BaseModel):
    id: int
    user_id: int
    cv_id: Optional[int] = None
    role: Optional[str] = None
    difficulty: Optional[str] = None
    status: str
    in_progress: bool
    history: list[InterviewTurnSchema] = Field(default_factory=list)
    running_score: Optional[float] = None
    overall_feedback: Optional[str] = None
    current_question: Optional[str] = None
    latest_feedback: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class InterviewStateRead(BaseModel):
    """Full resumable graph state payload."""

    session_id: Optional[int] = None
    user_id: Optional[int] = None
    cv_id: Optional[int] = None
    target_role: Optional[str] = None
    difficulty: Optional[str] = None
    status: Optional[str] = None
    history: list[InterviewTurnSchema] = Field(default_factory=list)
    current_question: Optional[str] = None
    running_score: Optional[float] = None
    score_count: int = 0
    latest_feedback: Optional[str] = None
    overall_feedback: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    node_log: list[dict[str, Any]] = Field(default_factory=list)


class InterviewUpdate(BaseModel):
    in_progress: Optional[bool] = None
    role: Optional[str] = None
    status: Optional[str] = None
    difficulty: Optional[str] = None
    overall_feedback: Optional[str] = None
