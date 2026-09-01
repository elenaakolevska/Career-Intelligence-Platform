import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.agents.workflow import (
    CAREER_GRAPH_ORDER,
    NODE_FAILURE_POLICY,
    build_career_graph,
    run_career_workflow,
    wrap_agent_node,
)
from app.agents.state import CareerGraphState, initial_state
from app.db import Base
from app.services.embedding_pipeline import embed_jobs_batch
from app.services.faiss_store import reset_stores
from app.services.user_service import UserService

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'cvs' / 'junior_backend.txt'


def test_failure_policy_documented():
    assert NODE_FAILURE_POLICY['cv_agent'] == 'halt'
    assert NODE_FAILURE_POLICY['job_matching_agent'] == 'continue'
    assert NODE_FAILURE_POLICY['report_agent'] == 'continue'
    assert CAREER_GRAPH_ORDER[0] == 'noop_bootstrap'
    assert CAREER_GRAPH_ORDER[-1] == 'noop_finish'
    assert 'report_agent' in CAREER_GRAPH_ORDER


def test_career_graph_compiles(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss'))
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        graph = build_career_graph(db)
        assert graph is not None
    finally:
        db.close()


def test_continue_policy_applies_safe_defaults():
    def boom(_state: CareerGraphState):
        raise RuntimeError('boom')

    wrapped = wrap_agent_node('job_matching_agent', boom)
    update = wrapped(initial_state(cv_id=1))
    assert update['ranked_jobs'] == []
    assert update.get('halted') is not True
    assert any('continue policy' in w for w in update['warnings'])
    assert update['node_log'][-1]['event'] == 'error'


def test_halt_policy_sets_halted_flag():
    def boom(_state: CareerGraphState):
        raise RuntimeError('cv exploded')

    wrapped = wrap_agent_node('cv_agent', boom)
    update = wrapped(initial_state(cv_id=1))
    assert update.get('halted') is True
    assert update.get('status') == 'failed'
    assert any('halt policy' in w for w in update['warnings'])


def test_e2e_workflow_on_fixture_cv(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss'))
    monkeypatch.setattr(settings, 'rerank_enabled', False)
    reset_stores()

    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        raw = FIXTURE.read_text(encoding='utf-8')
        user = UserService(db).create_user(email='workflow@example.com')
        structured = {
            'name': 'Alex Petrov',
            'email': 'alex.petrov@example.com',
            'summary': 'Junior backend developer with internship experience building REST APIs in Python.',
            'skills': ['Python', 'FastAPI', 'SQL', 'Git', 'Docker', 'Linux'],
            'experience': [
                {
                    'title': 'Backend Intern',
                    'company': 'SoftWave',
                    'description': 'Implemented FastAPI endpoints',
                }
            ],
            'education': [{'degree': 'BSc Computer Science', 'institution': 'University of Manchester'}],
            'location': 'Manchester, UK',
        }
        cv = models.CVProfile(
            user_id=user.id,
            status='completed',
            raw_text=raw,
            summary=structured['summary'],
            structured_data=json.dumps(structured),
            ats_score=78,
            ats_issues=json.dumps([]),
            extraction_method='native',
        )
        db.add(cv)
        jobs = [
            models.JobPosting(
                title='Backend Engineer FastAPI',
                description='Python FastAPI PostgreSQL Docker Kubernetes',
                company='Nimbus',
                external_id='w1',
                source='mock',
            ),
            models.JobPosting(
                title='Platform Engineer',
                description='Python Kubernetes Docker AWS Terraform',
                company='Stack',
                external_id='w2',
                source='mock',
            ),
            models.JobPosting(
                title='Junior Python Developer',
                description='Python SQL Git FastAPI Linux',
                company='Bright',
                external_id='w3',
                source='mock',
            ),
        ]
        for job in jobs:
            db.add(job)
        db.commit()
        db.refresh(cv)
        for job in jobs:
            db.refresh(job)
        embed_jobs_batch([j.id for j in jobs], db)

        result = run_career_workflow(db, cv_id=cv.id, user_id=user.id)
        state = result['state']

        assert result['total_ms'] >= 0
        assert isinstance(result['node_timings_ms'], dict)
        nodes = [e['node'] for e in result['node_log']]
        assert nodes == list(CAREER_GRAPH_ORDER)
        # Step-by-step diffs present on agent nodes
        agent_entries = [e for e in result['node_log'] if e['node'] in NODE_FAILURE_POLICY]
        assert any(e.get('state_diff') is not None or e.get('duration_ms') is not None for e in agent_entries)

        assert state.get('final_report')
        assert state['final_report']['cv_summary']['available'] is True
        assert state.get('status') == 'completed'
        assert state.get('halted') is False
    finally:
        db.close()
        reset_stores()
