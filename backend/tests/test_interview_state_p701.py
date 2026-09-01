"""P7-01: interview graph state, ORM mapping, and resume support."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base
from app.interview import (
    INTERVIEW_STATE_FIELD_OWNERS,
    InterviewGraphState,
    append_turn,
    build_noop_interview_graph,
    deserialize_interview_state,
    initial_interview_state,
    run_noop_interview_graph,
    serialize_interview_state,
)
from app.interview.persistence import apply_state_to_session, interview_session_to_state
from app.services.interview_service import InterviewService
from app.services.user_service import UserService


@pytest.fixture
def db_session():
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_interview_state_covers_required_fields_and_owners():
    required = {
        'session_id',
        'user_id',
        'target_role',
        'history',
        'running_score',
        'latest_feedback',
        'status',
        'node_log',
    }
    annotations = set(InterviewGraphState.__annotations__)
    assert required.issubset(annotations)
    for field in required:
        assert field in INTERVIEW_STATE_FIELD_OWNERS


def test_interview_state_json_roundtrip():
    state = initial_interview_state(user_id=1, target_role='Junior Java Developer')
    state = append_turn(
        state,
        question='Explain Spring Boot dependency injection.',
        answer='Annotations wire beans via the IoC container.',
        score=7.5,
        feedback='Solid high-level answer; add an example.',
    )
    payload = serialize_interview_state(state)
    restored = deserialize_interview_state(payload)
    assert restored['user_id'] == 1
    assert restored['target_role'] == 'Junior Java Developer'
    assert restored['history'][0]['score'] == 7.5
    assert restored['running_score'] == 7.5
    assert restored['score_count'] == 1
    assert restored['status'] == 'active'


def test_noop_interview_graph_compiles_and_runs():
    graph = build_noop_interview_graph()
    assert graph is not None
    result = run_noop_interview_graph(
        user_id=9, target_role='Backend Engineer', difficulty='junior'
    )
    assert result['user_id'] == 9
    assert result['target_role'] == 'Backend Engineer'
    assert result['status'] == 'active'
    nodes = [e['node'] for e in (result.get('node_log') or [])]
    assert nodes == ['noop_bootstrap', 'noop_finish']


def test_model_state_roundtrip_and_resume(db_session):
    user = UserService(db_session).create_user(email='interview@example.com')
    svc = InterviewService(db_session)
    created = svc.start_session(
        user.id, role='Junior Spring Boot Developer', difficulty='junior'
    )
    assert created.id > 0
    assert created.status == 'active'
    assert created.in_progress is True

    svc.record_turn_for_resume_test(
        created.id,
        question='What is a REST API?',
        answer='HTTP resource interface using verbs and status codes.',
        score=8.0,
        feedback='Clear definition.',
    )
    svc.record_turn_for_resume_test(
        created.id,
        question='How does Spring Security authenticate requests?',
    )

    # Simulate process restart: load from DB only
    row = db_session.query(models.InterviewSession).filter_by(id=created.id).one()
    assert row.history_json
    assert row.state_json
    assert row.running_score == 8.0

    resumed = svc.resume_session(created.id)
    assert resumed is not None
    assert resumed.id == created.id
    assert len(resumed.history) == 2
    assert resumed.history[0].answer
    assert resumed.history[1].answer is None
    assert resumed.current_question == 'How does Spring Security authenticate requests?'
    assert resumed.running_score == 8.0

    state = svc.load_state(created.id)
    assert state is not None
    assert state['session_id'] == created.id
    assert state['score_count'] == 1


def test_apply_state_to_session_maps_fields(db_session):
    user = UserService(db_session).create_user(email='map@example.com')
    session = models.InterviewSession(user_id=user.id, role='QA', status='pending', in_progress=True)
    db_session.add(session)
    db_session.flush()

    state = initial_interview_state(user_id=user.id, target_role='QA Engineer', session_id=session.id)
    state = append_turn(state, question='Describe a flaky test.', answer='Non-deterministic failure.', score=6.0)
    state['status'] = 'completed'
    state['overall_feedback'] = 'Practice more on CI stability.'
    apply_state_to_session(session, state)
    db_session.commit()
    db_session.refresh(session)

    assert session.in_progress is False
    assert session.status == 'completed'
    assert session.role == 'QA Engineer'
    assert session.overall_feedback.startswith('Practice')
    loaded = interview_session_to_state(session)
    assert loaded['running_score'] == 6.0
    assert loaded['history'][0]['question'] == 'Describe a flaky test.'
    # Full snapshot path
    assert json.loads(session.state_json)['overall_feedback'].startswith('Practice')
