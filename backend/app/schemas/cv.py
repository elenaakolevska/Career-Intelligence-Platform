from pydantic import BaseModel, ConfigDict
from typing import Optional


class CVCreate(BaseModel):
    user_id: int
    raw_text: Optional[str] = None


class CVUpdate(BaseModel):
    raw_text: Optional[str] = None
    summary: Optional[str] = None


class CVRead(BaseModel):
    id: int
    user_id: int
    raw_text: Optional[str] = None
    summary: Optional[str] = None
    filename: Optional[str] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


class CVUploadResponse(BaseModel):
    id: int
    status: str
    duplicate: bool = False
