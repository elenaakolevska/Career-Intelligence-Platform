from pydantic import BaseModel, ConfigDict
from typing import Optional


class InterviewCreate(BaseModel):
    user_id: int
    role: Optional[str] = None


class InterviewRead(BaseModel):
    id: int
    user_id: int
    role: Optional[str] = None
    in_progress: bool
    model_config = ConfigDict(from_attributes=True)


class InterviewUpdate(BaseModel):
    in_progress: Optional[bool] = None
    role: Optional[str] = None
