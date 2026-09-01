from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExperienceEntry(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class EducationEntry(BaseModel):
    degree: Optional[str] = None
    institution: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    details: Optional[str] = None


class StructuredCV(BaseModel):
    """Validated LLM extraction output for a CV."""

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    summary: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    location: Optional[str] = None

    @field_validator('skills', 'certifications', 'languages', mode='before')
    @classmethod
    def _coerce_str_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(',') if part.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator('experience', 'education', mode='before')
    @classmethod
    def _coerce_object_list(cls, value: Any) -> list:
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return value
        return []


class ATSIssue(BaseModel):
    code: str
    severity: str
    message: str


class ATSResult(BaseModel):
    score: int = Field(ge=0, le=100)
    issues: list[ATSIssue] = Field(default_factory=list)


class CVCreate(BaseModel):
    user_id: int
    raw_text: Optional[str] = None


class CVUpdate(BaseModel):
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = None


class CVRead(BaseModel):
    id: int
    user_id: int
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    filename: Optional[str] = None
    status: str
    extraction_method: Optional[str] = None
    error_message: Optional[str] = None
    structured_data: Optional[dict[str, Any]] = None
    ats_score: Optional[int] = None
    ats_issues: Optional[list[dict[str, Any]]] = None

    model_config = ConfigDict(from_attributes=True)


class CVUploadResponse(BaseModel):
    id: int
    status: str
    duplicate: bool = False
    ats_score: Optional[int] = None
