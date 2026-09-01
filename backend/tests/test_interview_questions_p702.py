"""P7-02: role-specific interview question generation + persistence."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.clients.llm_client import LLMClient
from app.db import Base
from app.interview import (
    generate_question_payload,
    initial_interview_state,
    nudge_difficulty,
    run_interview_question_graph,
    run_question_agent,
)
from app.interview.question_agent import normalize_difficulty
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


class _FakeLLM(LLMClient):
    def __init__(self, payloads: list[dict]):
        self.payloads = list(payloads)
        self.calls = 0

    def generate(self, prompt: str, **kwargs):
        self.calls += 1
        idx = min(self.calls - 1, len(self.payloads) - 1)
        return json.dumps(self.payloads[idx])


def test_nudge_difficulty_moves_one_step_toward_seniority():
    assert nudge_difficulty('junior', 'senior') == 'mid'
    assert nudge_difficulty('senior', 'junior') == 'mid'
    assert nudge_difficulty('mid', 'mid') == 'mid'
    assert nudge_difficulty('junior', None) == 'junior'
    assert normalize_difficulty('intermediate') == 'mid'


def test_stub_questions_are_role_specific_not_soft_skill():
    java_q = generate_question_payload(
        target_role='Junior Java Developer',
        difficulty='junior',
        previous_questions=[],
        seniority_context='n/a',
        variation_seed='seed-a',
    )
    py_q = generate_question_payload(
        target_role='Python Backend Engineer',
        difficulty='junior',
        previous_questions=[],
        seniority_context='n/a',
        variation_seed='seed-a',
    )
    assert 'java' in java_q['question'].lower() or 'arraylist' in java_q['question'].lower()
    assert 'python' in py_q['question'].lower() or 'list' in py_q['question'].lower()
    soft = ('tell me about yourself', 'strengths', 'weaknesses')
    for q in (java_q, py_q):
        low = q['question'].lower()
        assert not any(s in low for s in soft)
        assert len(q['question']) > 20


def test_questions_vary_across_calls_same_role():
    seen: list[str] = []
    previous: list[str] = []
    for i in range(3):
        payload = generate_question_payload(
            target_role='Junior Java Developer',
            difficulty='junior',
            previous_questions=previous,
            seniority_context='n/a',
            variation_seed=f'vary-{i}-{len(previous)}',
        )
        seen.append(payload['question'])
        previous.append(payload['question'])
    assert len(set(seen)) == 3


def test_difficulty_nudged_from_cv_seniority(db_session):
    user = UserService(db_session).create_user(email='senior-q@example.com')
    structured = {
        'name': 'Sam Senior',
        'summary': 'Staff engineer and tech lead',
        'skills': ['Java', 'Kubernetes'],
        'experience': [
            {
                'title': 'Senior Backend Engineer',
                'company': 'Acme',
                'description': 'Led platform team',
            },
            {
                'title': 'Staff Engineer',
                'company': 'Acme',
                'description': 'Architecture',
            },
        ],
    }
    cv = models.CVProfile(
        user_id=user.id,
        status='completed',
        summary='Staff engineer and tech lead',
        structured_data=json.dumps(structured),
    )
    db_session.add(cv)
    db_session.commit()
    db_session.refresh(cv)

    state = initial_interview_state(
        user_id=user.id,
        cv_id=cv.id,
        target_role='Java Platform Engineer',
        difficulty='junior',  # will be nudged up
    )
    updated = run_question_agent(state, db=db_session)
    assert updated['difficulty'] in {'mid', 'senior'}
    assert updated['history']
    assert updated['current_question']
    turn = updated['history'][0]
    assert turn['difficulty'] in {'mid', 'senior', 'junior'}
    # Senior bank questions mention architecture / JVM / messaging themes more often
    assert turn['question']


def test_generated_question_persisted_in_history(db_session):
    user = UserService(db_session).create_user(email='persist-q@example.com')
    svc = InterviewService(db_session)
    created = svc.start_session(
        user.id, role='Junior Spring Boot Developer', difficulty='junior'
    )
    result = svc.generate_next_question(created.id)
    assert result is not None
    assert result.current_question
    assert len(result.history) == 1
    assert result.history[0].answer is None
    assert result.history[0].question == result.current_question

    row = db_session.query(models.InterviewSession).filter_by(id=created.id).one()
    history = json.loads(row.history_json)
    assert history[0]['question'] == result.current_question
    snap = json.loads(row.state_json)
    assert snap['current_question'] == result.current_question

    # Unanswered → do not stack another question
    again = svc.generate_next_question(created.id)
    assert again is not None
    assert len(again.history) == 1


def test_llm_path_parses_json_and_stores_topics(db_session, monkeypatch):
    monkeypatch.setattr(
        'app.interview.question_agent.settings.llm_provider',
        'gemini',
        raising=False,
    )
    fake = _FakeLLM(
        [
            {
                'question': 'Explain Spring Boot auto-configuration for a Junior Java Developer service.',
                'topics': ['Spring Boot', 'auto-configuration'],
                'difficulty': 'junior',
                'rationale': 'Core Spring knowledge for the role.',
            }
        ]
    )
    user = UserService(db_session).create_user(email='llm-q@example.com')
    svc = InterviewService(db_session)
    created = svc.start_session(user.id, role='Junior Java Developer', difficulty='junior')
    result = svc.generate_next_question(created.id, llm=fake)
    assert result is not None
    assert fake.calls == 1
    assert 'Spring Boot' in result.history[0].question
    assert result.history[0].topics == ['Spring Boot', 'auto-configuration']


def test_interview_question_graph_runs():
    result = run_interview_question_graph(
        user_id=1,
        target_role='Python Backend Engineer',
        difficulty='mid',
    )
    nodes = [e['node'] for e in (result.get('node_log') or [])]
    assert 'noop_bootstrap' in nodes
    assert 'question_agent' in nodes
    assert result['current_question']
    assert len(result.get('history') or []) == 1
