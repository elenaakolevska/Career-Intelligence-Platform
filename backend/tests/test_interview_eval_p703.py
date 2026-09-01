"""P7-03: answer evaluation — score + written feedback referencing the question."""

from __future__ import annotations

import json
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.clients.llm_client import LLMClient
from app.db import Base
from app.interview import (
    append_turn,
    evaluate_answer,
    evaluate_answer_heuristic,
    initial_interview_state,
    run_evaluate_agent,
    run_interview_turn_graph,
)
from app.interview.evaluate_agent import _is_uncertainty_reply
from app.services.interview_service import InterviewService
from app.services.user_service import UserService

QUESTION = (
    'In Java, what is the difference between an ArrayList and a LinkedList, '
    'and when would you choose one over the other for a Junior Java Developer task?'
)

STRONG_ANSWER = (
    'An ArrayList is backed by a dynamic array with O(1) random access, while a LinkedList '
    'is a doubly linked list with O(n) indexing but cheaper inserts/removes in the middle. '
    'For example, I would pick ArrayList for most Junior Java Developer API payloads and '
    'read-heavy lists; I would choose LinkedList only when frequent mid-list mutations matter. '
    'The tradeoff is memory locality versus insert cost.'
)

WEAK_ANSWER = 'ArrayList is faster sometimes. LinkedList is different.'

OFF_TOPIC_ANSWER = (
    'I love pizza and my favourite colour is blue. Also my football team won last weekend.'
)


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


class _FakeEvalLLM(LLMClient):
    def generate(self, prompt: str, **kwargs):
        return json.dumps(
            {
                'score': 8.5,
                'feedback': (
                    'Regarding ArrayList vs LinkedList: solid coverage of access vs insert '
                    'tradeoffs for the question asked.'
                ),
                'strengths': ['Correct data-structure contrast'],
                'improvements': ['Mention iterator fail-fast behavior'],
                'relevance': 'on_topic',
            }
        )


def test_strong_weak_off_topic_scores_differentiated():
    strong = evaluate_answer_heuristic(question=QUESTION, answer=STRONG_ANSWER)
    weak = evaluate_answer_heuristic(question=QUESTION, answer=WEAK_ANSWER)
    off = evaluate_answer_heuristic(question=QUESTION, answer=OFF_TOPIC_ANSWER)

    assert strong['score'] > weak['score'] > off['score']
    assert strong['score'] >= 6.5
    assert weak['score'] <= 5.5
    assert off['score'] <= 2.0
    assert strong['relevance'] == 'on_topic'
    assert off['relevance'] == 'off_topic'

    # Feedback references the specific question
    for result in (strong, weak, off):
        fb = result['feedback'].lower()
        assert 'arraylist' in fb or 'linkedlist' in fb or 'regarding' in fb


def test_heuristic_judges_meaning_not_keyword_echo():
    """Pushback that only echoes the role title must not look 'on-topic' via word overlap."""
    question = (
        'Describe how HTTP request/response works end-to-end, and how a Youth Exchange '
        'Organizer would debug a 404 vs a 500 in an API.'
    )
    pushback = 'a youth exchange organizer shouldnt debug that'
    result = evaluate_answer_heuristic(
        question=question,
        answer=pushback,
        target_role='Youth Exchange Organizer',
    )
    assert result['score'] <= 3.5
    assert result['relevance'] in {'partial', 'off_topic'}
    fb = result['feedback'].lower()
    assert 'touched on' not in fb
    assert 'youth' not in fb or 'mismatch' in fb or 'premise' in fb or 'challenged' in fb
    # Must not celebrate echoed role words as strengths
    strengths_blob = ' '.join(result.get('strengths') or []).lower()
    assert 'youth' not in strengths_blob
    assert 'organizer' not in strengths_blob


def test_perfect_score_does_not_ask_for_edge_case_again():
    question = (
        'What is the difference between SQL and NoSQL databases, and when would you '
        'choose PostgreSQL?'
    )
    answer = (
        'SQL databases are relational with fixed schemas; NoSQL stores flexible documents or '
        'key-value data and often scales horizontally. For example, I pick PostgreSQL for '
        'transactions and joins; MongoDB or DynamoDB when schema changes fast. '
        'A useful edge case is that PostgreSQL JSONB can cover some semi-structured workloads '
        'without a separate NoSQL store. The tradeoff is operational complexity versus flexibility.'
    )
    result = evaluate_answer_heuristic(question=question, answer=answer, target_role='Junior ML developer')
    assert result['score'] >= 9.0
    fb = result['feedback'].lower()
    assert 'to score higher' not in fb
    assert 'call out one edge case' not in fb
    assert 'edge case' in fb or 'limitation' in fb or 'excellent' in fb


def test_dont_know_gets_teaching_and_motivation():
    question = (
        'Explain version control branching (feature branch → PR → main) as used by a '
        'team day to day.'
    )
    result = evaluate_answer_heuristic(question=question, answer="i dont know")
    assert result['score'] <= 2.0
    fb = result['feedback'].lower()
    assert 'honest' in fb or 'don’t know' in fb or "don't know" in fb or 'motivat' in fb or 'model answer' in fb
    assert 'feature branch' in fb or 'pull request' in fb or 'merge' in fb
    assert 'does not address what was asked' not in fb
    assert 'drifts away' not in fb


UNCERTAINTY_VARIATIONS = [
    'i am not really sure',
    'i am scared to answer',
    "I'm not comfortable answering this",
    'i am not confident in my knowledge on this topic',
    "I don't feel ready for this question",
    'this is outside my expertise',
    'I would need to look this up',
    "can't remember how this works",
    'drawing a blank right now',
    'not my strong area honestly',
    "I'm anxious about answering",
    'still unfamiliar with this subject',
    'my understanding is too limited here',
    'pass on this one',
    'first time hearing about this',
]


@pytest.mark.parametrize('answer', UNCERTAINTY_VARIATIONS)
def test_uncertainty_variations_are_coached_not_off_topic(answer):
    """Uncertainty is detected by signals/meaning, not a fixed sentence list."""
    question = (
        'What is the difference between SQL and NoSQL databases, and when would you '
        'choose PostgreSQL?'
    )
    assert _is_uncertainty_reply(answer) is True
    result = evaluate_answer_heuristic(question=question, answer=answer)
    assert result['score'] <= 2.0
    assert result['relevance'] == 'partial'
    fb = result['feedback'].lower()
    assert 'drifts away' not in fb
    assert 'does not engage' not in fb
    assert 'sql' in fb or 'postgres' in fb or 'nosql' in fb
    assert 'model answer' in fb or 'honest' in fb or 'confidence' in fb or 'nervous' in fb


def test_hedged_technical_answer_is_not_pure_uncertainty():
    """A real answer that starts with a hedge should still be scored as content."""
    question = (
        'What is the difference between SQL and NoSQL databases, and when would you '
        'choose PostgreSQL?'
    )
    answer = (
        "I'm not 100% sure, but SQL is relational with fixed schemas while NoSQL is more "
        'flexible for documents; I would choose PostgreSQL for transactions and joins.'
    )
    assert _is_uncertainty_reply(answer) is False
    result = evaluate_answer_heuristic(question=question, answer=answer)
    assert result['score'] >= 5.0
    assert result['relevance'] in {'on_topic', 'partial'}


def test_strong_feedback_cites_answer_content():
    question = (
        'What is the difference between SQL and NoSQL databases, and when would you '
        'choose PostgreSQL?'
    )
    answer = (
        'SQL databases are relational with fixed schemas; NoSQL stores flexible documents. '
        'For example, I pick PostgreSQL for transactions and joins. '
        'A useful edge case is that PostgreSQL JSONB can cover some semi-structured workloads.'
    )
    result = evaluate_answer_heuristic(question=question, answer=answer)
    assert result['score'] >= 8.0
    fb = result['feedback']
    assert 'PostgreSQL' in fb or 'SQL' in fb or 'JSONB' in fb or 'relational' in fb
    assert 'strong answer — clear reasoning' not in fb.lower() or 'strong point' in fb.lower()


def test_ml_role_avoids_repeating_same_stub_question():
    from app.interview.question_agent import _pick_stub_question

    previous: list[str] = []
    seen: list[str] = []
    for i in range(5):
        payload = _pick_stub_question(
            target_role='Junior ML developer',
            difficulty='junior',
            previous=previous,
            seed=f'seed-{i}',
        )
        q = payload['question']
        assert q not in seen
        seen.append(q)
        previous.append(q)
    # Should stay in ML/data topics rather than sticky HTTP-only
    blob = ' '.join(seen).lower()
    assert any(
        k in blob
        for k in (
            'overfit',
            'supervised',
            'precision',
            'feature',
            'classifier',
            'train',
            'validation',
            'missing',
            'bias',
            'confusion',
        )
    )
    assert '404' not in blob


def test_evaluation_latency_acceptable_for_live_flow():
    started = time.perf_counter()
    result = evaluate_answer(question=QUESTION, answer=STRONG_ANSWER)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert result['latency_ms'] < 500  # stub/heuristic path
    assert elapsed_ms < 500


def test_submit_answer_persists_score_and_feedback(db_session):
    user = UserService(db_session).create_user(email='eval@example.com')
    svc = InterviewService(db_session)
    created = svc.start_session(user.id, role='Junior Java Developer', difficulty='junior')
    asked = svc.generate_next_question(created.id)
    assert asked is not None
    assert asked.current_question

    scored = svc.submit_answer(created.id, STRONG_ANSWER)
    assert scored is not None
    assert scored.current_question is None
    assert len(scored.history) == 1
    turn = scored.history[0]
    assert turn.answer == STRONG_ANSWER
    assert turn.score is not None and turn.score >= 6.0
    assert turn.feedback
    assert 'regarding' in turn.feedback.lower() or 'arraylist' in turn.feedback.lower()
    assert scored.running_score == turn.score
    assert scored.latest_feedback == turn.feedback

    row = db_session.query(models.InterviewSession).filter_by(id=created.id).one()
    history = json.loads(row.history_json)
    assert history[0]['score'] == turn.score
    assert history[0]['feedback']


def test_submit_answer_requires_pending_question(db_session):
    user = UserService(db_session).create_user(email='nopending@example.com')
    svc = InterviewService(db_session)
    created = svc.start_session(user.id, role='Python Engineer')
    assert svc.submit_answer(created.id, 'anything') is None


def test_llm_eval_path(monkeypatch):
    monkeypatch.setattr(
        'app.interview.evaluate_agent.settings.llm_provider',
        'gemini',
        raising=False,
    )
    result = evaluate_answer(
        question=QUESTION,
        answer=STRONG_ANSWER,
        llm=_FakeEvalLLM(),
    )
    assert result['score'] == 8.5
    assert 'ArrayList' in result['feedback'] or 'arraylist' in result['feedback'].lower()


def test_run_evaluate_agent_updates_state():
    state = initial_interview_state(user_id=1, target_role='Junior Java Developer')
    state = append_turn(state, question=QUESTION)
    updated = run_evaluate_agent(state, answer=WEAK_ANSWER)
    assert updated['history'][0]['answer'] == WEAK_ANSWER
    assert updated['history'][0]['score'] is not None
    assert updated['latest_feedback']
    assert updated['current_question'] is None
    nodes = [e['node'] for e in (updated.get('node_log') or [])]
    assert 'evaluate_agent' in nodes


def test_interview_turn_graph_question_then_evaluate():
    result = run_interview_turn_graph(
        answer=STRONG_ANSWER,
        user_id=1,
        target_role='Junior Java Developer',
        difficulty='junior',
    )
    nodes = [e['node'] for e in (result.get('node_log') or [])]
    assert 'question_agent' in nodes
    assert 'evaluate_agent' in nodes
    assert result['history'][0]['answer'] == STRONG_ANSWER
    assert result['history'][0]['score'] is not None
