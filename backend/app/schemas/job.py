from pydantic import BaseModel, ConfigDict
from typing import Optional


class JobCreate(BaseModel):
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None


class JobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None


class JobRead(BaseModel):
    id: int
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
