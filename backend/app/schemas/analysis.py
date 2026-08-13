from pydantic import BaseModel, ConfigDict
from typing import Optional


class AnalysisCreate(BaseModel):
    cv_id: int


class AnalysisRead(BaseModel):
    id: int
    cv_id: int
    result: Optional[str] = None
    status: str
    model_config = ConfigDict(from_attributes=True)


class AnalysisUpdate(BaseModel):
    result: Optional[str] = None
    status: Optional[str] = None
