from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import ConfigDict
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
