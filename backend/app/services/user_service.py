from sqlalchemy.orm import Session

from app import models


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
