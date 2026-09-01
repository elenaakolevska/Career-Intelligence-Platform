"""Generate and persist CV/job embeddings into FAISS."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app import models
from app.services.cv_service import CVService
from app.services.embedding_service import build_cv_embedding_text, build_job_embedding_text, embed
from app.services.faiss_store import get_store

logger = logging.getLogger(__name__)


def embed_cv_profile(cv_id: int, db: Session) -> None:
    cv = db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
    if not cv:
        return
    structured = CVService.structured_as_dict(cv)
    text = build_cv_embedding_text(structured, cv.raw_text, cv.summary)
    if not text.strip():
        logger.warning('Skipping empty CV embedding for cv_id=%s', cv_id)
        return
    vector = embed(text)[0]
    store = get_store('cvs')
    store.add(str(cv_id), vector)
    logger.info('Embedded CV %s into FAISS (store size=%s)', cv_id, store.size)


def embed_job_posting(job_id: int, db: Session) -> None:
    job = db.query(models.JobPosting).filter(models.JobPosting.id == job_id).first()
    if not job:
        return
    text = build_job_embedding_text(job)
    vector = embed(text)[0]
    store = get_store('jobs')
    store.add(str(job_id), vector)


def embed_jobs_batch(job_ids: list[int], db: Session) -> int:
    jobs = db.query(models.JobPosting).filter(models.JobPosting.id.in_(job_ids)).all()
    if not jobs:
        return 0
    texts = [build_job_embedding_text(job) for job in jobs]
    vectors = embed(texts)
    store = get_store('jobs')
    for job, vector in zip(jobs, vectors):
        store.add(str(job.id), vector)
    return len(jobs)
