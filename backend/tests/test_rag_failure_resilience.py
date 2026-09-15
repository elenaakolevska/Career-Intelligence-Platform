"""RAG failure resilience: a broken RAG step must not halt the career analysis."""

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.agents.workflow import run_career_workflow
from app.db import Base
from app.services.embedding_pipeline import embed_jobs_batch
from app.services.faiss_store import reset_stores
from app.services.user_service import UserService


def _db():
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_cv(db):
    user = UserService(db).create_user(email='ragfail@example.com')
    cv = models.CVProfile(
        user_id=user.id,
        status='completed',
        raw_text='Python FastAPI SQL Git',
        summary='Junior backend developer',
        structured_data=json.dumps(
            {'name': 'Alex', 'skills': ['Python', 'FastAPI', 'SQL', 'Git'], 'summary': 'Junior backend developer'}
        ),
        ats_score=70,
        ats_issues='[]',
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


def _seed_jobs(db):
    for i, (title, desc) in enumerate(
        [
            ('Backend Engineer', 'Python FastAPI PostgreSQL Docker Kubernetes'),
            ('Platform Engineer', 'Python Kubernetes Docker AWS Terraform'),
            ('Data Engineer', 'Python Spark Airflow SQL'),
        ],
        start=1,
    ):
        db.add(models.JobPosting(title=title, description=desc, company=f'Co{i}', external_id=f'rf-{i}', source='mock'))
    db.commit()
    jobs = db.query(models.JobPosting).all()
    embed_jobs_batch([j.id for j in jobs], db)


def test_rag_failure_does_not_halt_analysis(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services.rag_pipeline import RagPipeline

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss'))
    monkeypatch.setattr(settings, 'rerank_enabled', False)
    monkeypatch.setattr(settings, 'adzuna_app_id', None)
    monkeypatch.setattr(settings, 'adzuna_use_mock', True)

    def boom(*args, **kwargs):
        raise RuntimeError('simulated RAG failure')

    monkeypatch.setattr(RagPipeline, 'run', boom)
    reset_stores()

    db = _db()
    try:
        cv = _seed_cv(db)
        _seed_jobs(db)
        result = run_career_workflow(db, cv_id=cv.id, user_id=cv.user_id)
        state = result['state']
        assert state['status'] == 'completed'
        assert state['halted'] is False
        assert state['final_report'] is not None
        # Deterministic results still produced; only RAG narratives are empty.
        assert state['retrieval_narratives'] == []
        assert state['sources'] == []
        assert isinstance(state['skill_gaps'], list)
        assert state['final_report']['insights'] == []
        assert state['final_report']['sources'] == []
    finally:
        db.close()
        reset_stores()
