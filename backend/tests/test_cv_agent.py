import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.agents.cv_agent import build_normalized_cv_summary, run_cv_agent
from app.agents.graph import build_cv_agent_graph, run_cv_agent_graph
from app.agents.state import initial_state
from app.db import Base
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


def _seed_cv(db, *, sparse: bool = False) -> models.CVProfile:
    user = UserService(db).create_user(email='cvagent@example.com')
    if sparse:
        cv = models.CVProfile(user_id=user.id, status='completed', raw_text=None, summary=None)
        db.add(cv)
        db.commit()
        db.refresh(cv)
        return cv

    structured = {
        'name': 'Alex Petrov',
        'email': 'alex@example.com',
        'summary': 'Junior backend developer',
        'skills': ['Python', 'FastAPI', 'SQL'],
        'experience': [
            {
                'title': 'Backend Intern',
                'company': 'SoftWave',
                'start_date': '2024',
                'end_date': '2024',
                'description': 'Built FastAPI endpoints',
            }
        ],
        'education': [{'degree': 'BSc CS', 'institution': 'UoM'}],
        'location': 'Manchester, UK',
    }
    cv = models.CVProfile(
        user_id=user.id,
        status='completed',
        raw_text='Alex Petrov\nPython FastAPI SQL',
        summary='Junior backend developer',
        structured_data=json.dumps(structured),
        ats_score=82,
        ats_issues=json.dumps([{'code': 'too_long', 'severity': 'low', 'message': 'Slightly long'}]),
        extraction_method='native',
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


def test_normalized_summary_includes_skills_and_experience(db_session):
    cv = _seed_cv(db_session)
    summary = build_normalized_cv_summary(cv)
    assert 'Alex Petrov' in summary
    assert 'Python' in summary
    assert 'Backend Intern' in summary
    assert 'BSc CS' in summary


def test_sparse_cv_does_not_crash(db_session):
    cv = _seed_cv(db_session, sparse=True)
    summary = build_normalized_cv_summary(cv)
    assert 'Sparse CV' in summary or 'none extracted' in summary or 'No CV' in summary


def test_cv_agent_populates_expected_state_keys(db_session):
    cv = _seed_cv(db_session)
    state = initial_state(cv_id=cv.id, user_id=cv.user_id)
    update = run_cv_agent(state, db_session)

    for key in ('cv_summary', 'structured_cv', 'ats_score', 'ats_issues', 'node_log', 'status'):
        assert key in update

    assert update['cv_summary']
    assert 'Python' in update['cv_summary']
    assert update['structured_cv']['name'] == 'Alex Petrov'
    assert update['ats_score'] == 82
    assert isinstance(update['ats_issues'], list)
    assert update['node_log'][-1]['node'] == 'cv_agent'
    assert update['node_log'][-1]['event'] == 'completed'


def test_cv_agent_handles_missing_cv_id(db_session):
    state = initial_state(cv_id=None)
    update = run_cv_agent(state, db_session)
    assert update['cv_summary'] == 'No CV profile available.'
    assert update['structured_cv'] is None
    assert any('missing cv_id' in w for w in update['warnings'])


def test_cv_agent_handles_missing_profile(db_session):
    state = initial_state(cv_id=99999)
    update = run_cv_agent(state, db_session)
    assert update['cv_summary'] == 'No CV profile available.'
    assert any('not found' in w for w in update['warnings'])


def test_cv_agent_graph_runs_end_to_end(db_session):
    cv = _seed_cv(db_session)
    graph = build_cv_agent_graph(db_session)
    assert graph is not None
    result = run_cv_agent_graph(db_session, cv_id=cv.id, user_id=cv.user_id)
    assert result['status'] == 'completed'
    assert result['cv_summary'] and 'Alex Petrov' in result['cv_summary']
    assert result['structured_cv'] is not None
    assert result['ats_score'] == 82
    nodes = [e['node'] for e in result['node_log']]
    assert nodes == ['noop_bootstrap', 'cv_agent', 'noop_finish']
