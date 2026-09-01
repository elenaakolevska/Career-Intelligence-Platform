"""JWT auth routes: register, login, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ValidationError
from app.schemas.auth import AuthUserRead, LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/register', response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user, token = AuthService(db).register(
            email=str(payload.email).lower().strip(),
            password=payload.password,
            full_name=payload.full_name,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    return TokenResponse(
        access_token=token,
        user=AuthUserRead.model_validate(user),
    )


@router.post('/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, token = AuthService(db).login(
            email=str(payload.email).lower().strip(),
            password=payload.password,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=401, detail=exc.detail) from exc
    return TokenResponse(
        access_token=token,
        user=AuthUserRead.model_validate(user),
    )


@router.get('/me', response_model=AuthUserRead)
def me(current_user=Depends(get_current_user)):
    return AuthUserRead.model_validate(current_user)
