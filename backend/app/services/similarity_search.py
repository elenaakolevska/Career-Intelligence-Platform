"""Similarity search: CV embedding -> top-N JobPosting matches."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.core.config import settings
from app.services.cv_service import CVService
from app.services.embedding_pipeline import embed_cv_profile
from app.services.embedding_service import build_cv_embedding_text, embed
from app.services.faiss_store import get_store

logger = logging.getLogger(__name__)


def search_jobs_for_cv(db: Session, cv_id: int, top_k: int | None = None) -> list[dict[str, Any]]:
    k = top_k if top_k is not None else settings.similarity_top_k
    k = max(1, min(int(k), 50))

    cv = db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
    if not cv:
        return []

    # Ensure CV vector exists
    cv_store = get_store('cvs')
    job_store = get_store('jobs')
    if job_store.size == 0:
        return []

    structured = CVService.structured_as_dict(cv)
    text = build_cv_embedding_text(structured, cv.raw_text, cv.summary)
    vector = embed(text)[0]
    # Refresh CV index entry
    cv_store.add(str(cv_id), vector)

    hits = job_store.search(vector, top_k=k)
    if not hits:
        return []

    job_ids = [int(jid) for jid, _ in hits]
    jobs = {
        job.id: job
        for job in db.query(models.JobPosting).filter(models.JobPosting.id.in_(job_ids)).all()
    }
    ranked: list[dict[str, Any]] = []
    for jid, score in hits:
        job = jobs.get(int(jid))
        if not job:
            continue
        ranked.append(
            {
                'job_id': job.id,
                'score': score,
                'title': job.title,
                'company': job.company,
                'location': job.location,
                'url': job.url,
                'description': job.description,
            }
        )
    return ranked
