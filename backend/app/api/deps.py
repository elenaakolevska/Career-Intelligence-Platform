from typing import Generator

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import models
from app.core.security import decode_access_token
from app.db import SessionLocal

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail='Not authenticated')
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload.get('sub', 0))
    except Exception:
        raise HTTPException(status_code=401, detail='Invalid or expired token') from None
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail='User not found')
    return user


def require_cv_owner(cv_id: int, user: models.User, db: Session) -> models.CVProfile:
    cv = db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
    if not cv:
        raise HTTPException(status_code=404, detail='CV not found')
    if cv.user_id != user.id:
        raise HTTPException(status_code=403, detail='Not allowed to access this CV')
    return cv
