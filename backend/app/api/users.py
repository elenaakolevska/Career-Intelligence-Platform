from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.api.deps import get_current_user, get_db
from app.core.exceptions import ValidationError
from app.schemas.user import PasswordChange, UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix='/users', tags=['users'])


@router.post('/', response_model=UserRead)
def create_user(
    payload: UserCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = UserService(db)
    user = svc.create_user(email=payload.email, full_name=payload.full_name)
    return user


@router.patch('/me', response_model=UserRead)
def update_me(
    payload: UserUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return UserService(db).update_user(
            current_user,
            full_name=payload.full_name,
            email=payload.email,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc


@router.post('/me/password')
def change_my_password(
    payload: PasswordChange,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        UserService(db).change_password(
            current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    return {'ok': True}


@router.get('/{user_id}', response_model=UserRead)
def get_user(
    user_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a user profile; only the authenticated user's own profile."""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail='Not allowed to access this user')
    svc = UserService(db)
    user = svc.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user
