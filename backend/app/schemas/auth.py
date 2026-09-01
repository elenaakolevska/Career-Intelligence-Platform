from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: 'AuthUserRead'


class AuthUserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


TokenResponse.model_rebuild()
