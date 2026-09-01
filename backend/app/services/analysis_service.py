from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app import models
from app.agents.workflow import run_career_workflow
from app.services.jobs_service import JobsService

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _ensure_jobs_indexed(self) -> None:
        """Seed mock jobs when the corpus is empty so matching/analysis can run offline."""
        count = self.db.query(models.JobPosting).count()
        if count > 0:
            return
        logger.info('No job postings found; seeding mock corpus before analysis')
        JobsService(self.db).seed_mock_jobs()

    def analyze(self, cv_id: int) -> dict:
        cv = self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
        if not cv:
            return {'cv_id': cv_id, 'status': 'failed', 'error': 'CV not found'}

        row = models.AnalysisResult(cv_id=cv_id, status='pending', result=None)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        try:
            self._ensure_jobs_indexed()
            result = run_career_workflow(self.db, cv_id=cv_id, user_id=cv.user_id)
            state = result['state']
            payload = {
                'id': row.id,
                'cv_id': cv_id,
                'status': state.get('status') or 'completed',
                'halted': state.get('halted', False),
                'total_ms': result['total_ms'],
                'node_timings_ms': result['node_timings_ms'],
                'node_log': result['node_log'],
                'final_report': state.get('final_report'),
                'warnings': state.get('warnings') or [],
                'errors': state.get('errors') or [],
            }
            row.status = 'completed' if not state.get('halted') else 'completed'
            if state.get('status') == 'failed' or (state.get('errors') and not state.get('final_report')):
                row.status = 'failed'
            row.result = json.dumps(payload, ensure_ascii=False, default=str)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
            payload['analysis_id'] = row.id
            payload['persisted_status'] = row.status
            return payload
        except Exception as exc:
            logger.exception('Analysis failed for cv_id=%s', cv_id)
            fail_payload = {
                'id': row.id,
                'cv_id': cv_id,
                'status': 'failed',
                'error': str(exc),
                'final_report': None,
                'warnings': [],
                'errors': [str(exc)],
            }
            row.status = 'failed'
            row.result = json.dumps(fail_payload, ensure_ascii=False, default=str)
            self.db.add(row)
            self.db.commit()
            return fail_payload

    def get_latest(self, cv_id: int) -> dict | None:
        row = (
            self.db.query(models.AnalysisResult)
            .filter(models.AnalysisResult.cv_id == cv_id)
            .order_by(models.AnalysisResult.created_at.desc(), models.AnalysisResult.id.desc())
            .first()
        )
        if not row:
            return None
        return self._row_to_payload(row)

    def get_by_id(self, analysis_id: int) -> dict | None:
        row = self.db.query(models.AnalysisResult).filter(models.AnalysisResult.id == analysis_id).first()
        if not row:
            return None
        return self._row_to_payload(row)

    def _row_to_payload(self, row: models.AnalysisResult) -> dict:
        parsed: dict = {}
        if row.result:
            try:
                parsed = json.loads(row.result)
            except json.JSONDecodeError:
                parsed = {'raw': row.result}
        return {
            **parsed,
            'analysis_id': row.id,
            'cv_id': row.cv_id,
            'persisted_status': row.status,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        }
