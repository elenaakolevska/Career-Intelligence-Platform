"""Register / login for SkillBridge."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app import models
from app.core.exceptions import ValidationError
from app.core.security import create_access_token, hash_password, verify_password


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def register(self, *, email: str, password: str, full_name: str | None = None) -> tuple[models.User, str]:
        existing = self.db.query(models.User).filter(models.User.email == email).first()
        if existing and existing.password_hash:
            raise ValidationError('An account with this email already exists')
        if existing and not existing.password_hash:
            # Upgrade legacy demo user row
            existing.password_hash = hash_password(password)
            if full_name:
                existing.full_name = full_name
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            token = create_access_token(subject=existing.id, extra={'email': existing.email})
            return existing, token

        user = models.User(
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        token = create_access_token(subject=user.id, extra={'email': user.email})
        return user, token

    def login(self, *, email: str, password: str) -> tuple[models.User, str]:
        user = self.db.query(models.User).filter(models.User.email == email).first()
        if not user or not verify_password(password, user.password_hash):
            raise ValidationError('Invalid email or password')
        token = create_access_token(subject=user.id, extra={'email': user.email})
        return user, token
