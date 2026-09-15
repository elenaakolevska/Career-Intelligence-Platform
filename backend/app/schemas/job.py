from pydantic import BaseModel, ConfigDict
from typing import Optional


class JobRead(BaseModel):
    id: int
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_raw: Optional[str] = None
    external_id: Optional[str] = None
    source: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)
