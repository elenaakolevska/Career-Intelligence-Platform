from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.schemas.cv import ATSResult, StructuredCV


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
        extraction_method: str | None = None,
    ) -> models.CVProfile:
        cv = models.CVProfile(
            user_id=user_id,
            raw_text=raw_text,
            filename=filename,
            status=status,
            extraction_method=extraction_method,
        )
        self.db.add(cv)
        self.db.commit()
        self.db.refresh(cv)
        return cv

    def update_cv_text(
        self,
        cv_id: int,
        raw_text: str,
        status: str = 'completed',
        *,
        extraction_method: str | None = None,
        error_message: str | None = None,
    ) -> models.CVProfile:
        cv = self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
        if not cv:
            raise ValueError(f'CVProfile {cv_id} not found')
        cv.raw_text = raw_text
        cv.status = status
        if extraction_method is not None:
            cv.extraction_method = extraction_method
        if error_message is not None:
            cv.error_message = error_message
        self.db.commit()
        self.db.refresh(cv)
        return cv

    def mark_failed(self, cv_id: int, error_message: str) -> models.CVProfile:
        cv = self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
        if not cv:
            raise ValueError(f'CVProfile {cv_id} not found')
        cv.status = 'failed'
        cv.error_message = error_message
        self.db.commit()
        self.db.refresh(cv)
        return cv

    def save_structured(
        self,
        cv_id: int,
        structured: StructuredCV,
        *,
        ats: ATSResult | None = None,
        status: str = 'completed',
    ) -> models.CVProfile:
        cv = self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
        if not cv:
            raise ValueError(f'CVProfile {cv_id} not found')
        payload = structured.model_dump()
        cv.structured_data = json.dumps(payload)
        cv.summary = structured.summary
        cv.status = status
        cv.error_message = None
        if ats is not None:
            cv.ats_score = ats.score
            cv.ats_issues = json.dumps([issue.model_dump() for issue in ats.issues])
        self.db.commit()
        self.db.refresh(cv)
        return cv

    def get_cv(self, cv_id: int) -> models.CVProfile | None:
        return self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()

    def get_cv_by_user_and_filename(self, user_id: int, filename: str) -> models.CVProfile | None:
        return (
            self.db.query(models.CVProfile)
            .filter(models.CVProfile.user_id == user_id, models.CVProfile.filename == filename)
            .first()
        )

    @staticmethod
    def structured_as_dict(cv: models.CVProfile) -> dict[str, Any] | None:
        if not cv.structured_data:
            return None
        try:
            return json.loads(cv.structured_data)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def ats_issues_as_list(cv: models.CVProfile) -> list[dict[str, Any]] | None:
        if not cv.ats_issues:
            return None
        try:
            return json.loads(cv.ats_issues)
        except json.JSONDecodeError:
            return None
