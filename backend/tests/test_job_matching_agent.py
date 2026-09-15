import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.agents.cv_agent import run_cv_agent
from app.agents.graph import build_matching_graph, run_matching_graph
from app.agents.job_matching_agent import RANKED_JOB_KEYS, normalize_ranked_job, run_job_matching_agent
from app.agents.state import initial_state
from app.db import Base
from app.services.embedding_pipeline import embed_jobs_batch
from app.services.faiss_store import reset_stores
from app.services.reranker import rerank_jobs
from app.services.user_service import UserService


@pytest.fixture
def db_session():
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Sess = sessionmaker(bind=engine)
    session = Sess()
    yield session
    session.close()


@pytest.fixture
def isolated_index(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss'))
    monkeypatch.setattr(settings, 'rerank_enabled', False)
    # Hermetic: never enter live-Adzuna mode, which filters out mock sources.
    monkeypatch.setattr(settings, 'adzuna_app_id', None)
    monkeypatch.setattr(settings, 'adzuna_use_mock', True)
    reset_stores()
    yield
    reset_stores()


def _seed_cv(db) -> models.CVProfile:
    user = UserService(db).create_user(email='match@example.com')
    structured = {
        'name': 'Alex Petrov',
        'summary': 'Junior backend developer with Python FastAPI',
        'skills': ['Python', 'FastAPI', 'SQL', 'Docker'],
        'experience': [{'title': 'Backend Intern', 'company': 'SoftWave', 'description': 'FastAPI APIs'}],
    }
    cv = models.CVProfile(
        user_id=user.id,
        status='completed',
        raw_text='Alex Petrov Python FastAPI SQL Docker',
        summary='Junior backend developer with Python FastAPI',
        structured_data=json.dumps(structured),
        ats_score=80,
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


def _seed_jobs(db) -> list[models.JobPosting]:
    rows = [
        models.JobPosting(
            title='Backend Engineer FastAPI',
            company='Nimbus',
            location='London',
            description='Python FastAPI PostgreSQL Docker REST APIs',
            url='https://example.com/1',
            external_id='jm-1',
            source='mock',
        ),
        models.JobPosting(
            title='Pastry Chef',
            company='BakeHouse',
            location='Paris',
            description='Croissants pastry baking recipes kitchen',
            url='https://example.com/2',
            external_id='jm-2',
            source='mock',
        ),
        models.JobPosting(
            title='Junior Python Developer',
            company='BrightStart',
            location='Manchester',
            description='Python SQL Git backend services FastAPI basics',
            url='https://example.com/3',
            external_id='jm-3',
            source='mock',
        ),
    ]
    for row in rows:
        db.add(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    embed_jobs_batch([row.id for row in rows], db)
    return rows


def test_normalize_ranked_job_shape():
    normalized = normalize_ranked_job(
        {'job_id': 1, 'score': 0.9, 'title': 'Eng', 'company': 'X', 'extra': 'drop'}
    )
    for key in RANKED_JOB_KEYS:
        assert key in normalized
    assert 'extra' not in normalized


def test_job_matching_agent_writes_ranked_jobs(db_session, isolated_index):
    cv = _seed_cv(db_session)
    _seed_jobs(db_session)

    state = initial_state(cv_id=cv.id, user_id=cv.user_id)
    state.update(run_cv_agent(state, db_session))
    update = run_job_matching_agent(state, db_session)

    assert 'ranked_jobs' in update
    assert isinstance(update['ranked_jobs'], list)
    assert update['ranked_jobs'], 'expected at least one match'
    for job in update['ranked_jobs']:
        for key in RANKED_JOB_KEYS:
            assert key in job
        assert isinstance(job['score'], float)
    # Top match should be backend-related for a Python/FastAPI CV
    assert 'Python' in (update['ranked_jobs'][0]['description'] or '') or 'FastAPI' in (
        update['ranked_jobs'][0]['title'] or ''
    )
    assert update['node_log'][-1]['node'] == 'job_matching_agent'


def test_job_matching_zero_matches_does_not_break(db_session, isolated_index, monkeypatch):
    from app.core.config import settings
    from app.agents import job_matching_agent as jma

    cv = _seed_cv(db_session)
    # Empty job index, and prevent mock seeding from populating search hits
    monkeypatch.setattr(jma, 'search_jobs_for_cv', lambda *a, **k: [])
    monkeypatch.setattr(settings, 'adzuna_use_mock', True)

    state = initial_state(cv_id=cv.id)
    state['cv_summary'] = 'Some summary'
    # Pretend jobs already exist so seed path is skipped, search returns []
    db_session.add(
        models.JobPosting(title='Unindexed', company='Z', description='zzz', external_id='u1', source='mock')
    )
    db_session.commit()

    update = run_job_matching_agent(state, db_session)
    assert update['ranked_jobs'] == []
    assert any('zero matches' in w for w in update['warnings'])
    assert update.get('status') == 'running'


def test_seniority_adjustment_penalizes_staff_for_juniors():
    from app.agents.job_matching_agent import apply_seniority_adjustment, estimate_candidate_level

    level = estimate_candidate_level(
        {
            'education': [{'institution': 'FINKI'}],
            'experience': [{'title': 'Student Connect Project', 'company': None}],
        },
        'Elena student Python developer',
    )
    assert level == 'junior'
    matches = [
        {'job_id': 1, 'score': 0.9, 'title': 'Staff Software Engineer', 'description': 'Lead platform'},
        {'job_id': 2, 'score': 0.5, 'title': 'Junior Python Developer', 'description': 'Entry-level Python'},
        {'job_id': 3, 'score': 0.55, 'title': 'Software Engineer', 'description': 'Python APIs'},
    ]
    adjusted = apply_seniority_adjustment(matches, candidate_level='junior')
    assert adjusted[0]['job_id'] == 2
    assert adjusted[-1]['job_id'] == 1


def test_extract_skills_aliases_and_cloud_terms():
    from app.agents.skill_utils import extract_skills_from_text

    text = 'Microsoft Azure Storage, Spring Boot microservices, C# and application security'
    skills = extract_skills_from_text(text)
    assert 'Azure' in skills
    assert 'Spring Boot' in skills
    assert 'C#' in skills
    assert 'security' in skills


def test_rerank_reorders_when_enabled(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'rerank_enabled', True)
    candidates = [
        {'job_id': 1, 'score': 0.99, 'title': 'Chef', 'description': 'pastry baking kitchen'},
        {'job_id': 2, 'score': 0.1, 'title': 'Python Engineer', 'description': 'Python FastAPI backend'},
    ]
    reranked = rerank_jobs('Python FastAPI backend engineer', candidates, enabled=True)
    assert reranked[0]['job_id'] == 2
    assert reranked[0].get('reranked') is True


def test_matching_graph_runs_cv_then_jobs(db_session, isolated_index):
    cv = _seed_cv(db_session)
    _seed_jobs(db_session)
    graph = build_matching_graph(db_session)
    assert graph is not None
    result = run_matching_graph(db_session, cv_id=cv.id, user_id=cv.user_id)
    assert result['status'] == 'completed'
    assert result['cv_summary']
    assert isinstance(result['ranked_jobs'], list)
    assert result['ranked_jobs']
    nodes = [e['node'] for e in result['node_log']]
    assert nodes == ['noop_bootstrap', 'cv_agent', 'job_matching_agent', 'noop_finish']
