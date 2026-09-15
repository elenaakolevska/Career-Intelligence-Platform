from sqlalchemy.orm import Session

from app import models
from app.core.exceptions import ValidationError
from app.core.security import hash_password, verify_password


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user(self, email: str, full_name: str | None = None) -> models.User:
        existing = self.db.query(models.User).filter(models.User.email == email).first()
        if existing:
            return existing
        user = models.User(email=email, full_name=full_name)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user(self, user_id: int) -> models.User | None:
        return self.db.query(models.User).filter(models.User.id == user_id).first()

    def update_user(
        self,
        user: models.User,
        *,
        full_name: str | None = None,
        email: str | None = None,
    ) -> models.User:
        if email is not None:
            normalized = str(email).lower().strip()
            if not normalized:
                raise ValidationError('Email cannot be empty')
            taken = (
                self.db.query(models.User)
                .filter(models.User.email == normalized, models.User.id != user.id)
                .first()
            )
            if taken:
                raise ValidationError('Email is already in use')
            user.email = normalized
        if full_name is not None:
            user.full_name = full_name.strip() or None
        self.db.commit()
        self.db.refresh(user)
        return user

    def change_password(
        self,
        user: models.User,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise ValidationError('Current password is incorrect')
        if len(new_password) < 8:
            raise ValidationError('New password must be at least 8 characters')
        user.password_hash = hash_password(new_password)
        self.db.commit()
