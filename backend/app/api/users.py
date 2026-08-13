from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix='/users', tags=['users'])


@router.post('/', response_model=UserRead)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    svc = UserService(db)
    user = svc.create_user(email=payload.email, full_name=payload.full_name)
    return user


@router.get('/{user_id}', response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    svc = UserService(db)
    user = svc.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user
