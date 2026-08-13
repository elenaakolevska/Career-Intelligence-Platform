from sqlalchemy.orm import Session

from app import models


class CVService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_cv(
        self,
        user_id: int,
        *,
        raw_text: str | None = None,
        filename: str | None = None,
        status: str = 'pending',
    ) -> models.CVProfile:
        cv = models.CVProfile(user_id=user_id, raw_text=raw_text, filename=filename, status=status)
        self.db.add(cv)
        self.db.commit()
        self.db.refresh(cv)
        return cv

    def update_cv_text(self, cv_id: int, raw_text: str, status: str = 'completed') -> models.CVProfile:
        cv = self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
        if not cv:
            raise ValueError(f'CVProfile {cv_id} not found')
        cv.raw_text = raw_text
        cv.status = status
        self.db.commit()
        self.db.refresh(cv)
        return cv

    def get_cv(self, cv_id: int) -> models.CVProfile | None:
        return self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()

    def get_cv_by_user_and_filename(
        self, user_id: int, filename: str
    ) -> models.CVProfile | None:
        return (
            self.db.query(models.CVProfile)
            .filter(models.CVProfile.user_id == user_id, models.CVProfile.filename == filename)
            .first()
        )
