from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.clients.adzuna_client import AdzunaClient
from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.data.mock_jobs import MOCK_JOBS, select_mock_jobs_for_profile
from app.schemas.job import JobRead
from app.services.cv_service import CVService
from app.services.embedding_pipeline import embed_jobs_batch
from app.services.job_normalizer import normalize_adzuna_job
from app.services.job_query_builder import build_job_query
from app.services.similarity_search import search_jobs_for_cv

logger = logging.getLogger(__name__)


def _redis_client():
    try:
        import redis

        return redis.from_url(settings.redis_url, socket_connect_timeout=1)
    except Exception:
        return None


def _cache_get(key: str) -> Any | None:
    client = _redis_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        logger.warning('Redis cache get failed; continuing without cache', exc_info=True)
    return None


def _cache_set(key: str, value: Any, ttl: int) -> None:
    client = _redis_client()
    if client is None:
        return
    try:
        client.setex(key, ttl, json.dumps(value))
    except Exception:
        logger.warning('Redis cache set failed; continuing without cache', exc_info=True)


class JobsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_jobs(self) -> list[JobRead]:
        rows = self.db.query(models.JobPosting).order_by(models.JobPosting.id.desc()).limit(100).all()
        return [JobRead.model_validate(row) for row in rows]

    def upsert_job(self, data: dict[str, Any]) -> models.JobPosting:
        existing = None
        if data.get('external_id'):
            existing = (
                self.db.query(models.JobPosting)
                .filter(
                    models.JobPosting.external_id == data['external_id'],
                    models.JobPosting.source == data.get('source'),
                )
                .first()
            )
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
            self.db.commit()
            self.db.refresh(existing)
            return existing
        job = models.JobPosting(**data)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def seed_mock_jobs(self) -> list[models.JobPosting]:
        jobs = [self.upsert_job(dict(item)) for item in MOCK_JOBS]
        embed_jobs_batch([job.id for job in jobs], self.db)
        return jobs

    def ensure_corpus_for_cv(self, cv_id: int) -> list[models.JobPosting]:
        """Populate the local job corpus: live Adzuna when configured, else mock."""
        if settings.adzuna_use_mock or not settings.adzuna_app_id:
            return self.seed_mock_jobs()
        return self.fetch_and_store_for_cv(cv_id)

    def fetch_and_store_for_cv(self, cv_id: int, *, results_per_page: int = 20) -> list[models.JobPosting]:
        cv = self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
        if not cv:
            return []
        structured = CVService.structured_as_dict(cv)
        query = build_job_query(structured)
        cache_key = 'adzuna:' + hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()

        if settings.adzuna_use_mock or not settings.adzuna_app_id:
            mock_slice = select_mock_jobs_for_profile(structured, limit=results_per_page)
            results = [normalize_adzuna_job(dict(item), source=item.get('source') or 'mock') for item in mock_slice]
        else:
            cached = _cache_get(cache_key)
            if cached is not None:
                results = cached
            else:
                try:
                    client = AdzunaClient()
                    results = self._search_adzuna_with_backoff(
                        client,
                        what=query['what'],
                        where=query['where'] or None,
                        results_per_page=results_per_page,
                        structured=structured,
                    )
                    _cache_set(cache_key, results, settings.adzuna_cache_ttl_seconds)
                except ExternalServiceError:
                    logger.exception('Adzuna failed; falling back to mock jobs')
                    mock_slice = select_mock_jobs_for_profile(structured, limit=results_per_page)
                    results = [
                        normalize_adzuna_job(dict(item), source=item.get('source') or 'mock')
                        for item in mock_slice
                    ]

        jobs = [self.upsert_job(item) for item in results]
        embed_jobs_batch([job.id for job in jobs], self.db)
        return jobs

    def _search_adzuna_with_backoff(
        self,
        client: AdzunaClient,
        *,
        what: str,
        where: str | None,
        results_per_page: int,
        structured: dict | None,
    ) -> list[dict]:
        """Search Adzuna; broaden query if the first attempt returns nothing."""
        attempts: list[tuple[str, str | None]] = [(what, where)]
        if where:
            attempts.append((what, None))
        skills = [str(s) for s in ((structured or {}).get('skills') or []) if s][:3]
        broad = ' '.join(skills) if skills else 'software developer'
        if broad and broad != what:
            attempts.append((broad, None))
        attempts.append(('software developer python', None))

        seen: set[tuple[str, str | None]] = set()
        for attempt_what, attempt_where in attempts:
            key = (attempt_what, attempt_where)
            if key in seen:
                continue
            seen.add(key)
            payload = client.search(
                what=attempt_what,
                where=attempt_where,
                results_per_page=results_per_page,
            )
            raw = payload.get('results') or []
            logger.info(
                'Adzuna search what=%r where=%r count=%s',
                attempt_what,
                attempt_where,
                len(raw),
            )
            if raw:
                return [normalize_adzuna_job(item) for item in raw]
        return []

    def match_for_cv(self, cv_id: int, top_k: int | None = None) -> list[dict[str, Any]]:
        # Ensure we have jobs to search
        if self.db.query(models.JobPosting).count() == 0:
            self.ensure_corpus_for_cv(cv_id)
        k = top_k or settings.similarity_top_k
        # Over-fetch then apply the same seniority adjustment used by the Job Matching agent
        from app.agents.job_matching_agent import apply_seniority_adjustment, estimate_candidate_level

        cv = self.db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
        structured = CVService.structured_as_dict(cv) if cv else {}
        summary = (cv.summary if cv else None) or ''
        level = estimate_candidate_level(structured, summary)
        matches = search_jobs_for_cv(self.db, cv_id, top_k=max(k * 3, k))
        matches = apply_seniority_adjustment(matches, candidate_level=level)
        return matches[:k]
