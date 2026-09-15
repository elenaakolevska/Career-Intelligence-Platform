"""P7-04 WebSocket interview + P7-05 history persistence."""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_db
from app.db import Base
from app.main import app


@pytest.fixture
def engine():
    eng = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db_session(engine):
    Sess = sessionmaker(bind=engine)
    session = Sess()
    yield session
    session.close()


@pytest.fixture
def client(engine, monkeypatch):
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # WebSocket handler opens its own sessions â€” point at the same in-memory engine
    monkeypatch.setattr('app.interview.ws_handler.SessionLocal', TestingSessionLocal)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register(client: TestClient, email: str) -> tuple[str, dict]:
    resp = client.post(
        '/api/v1/auth/register',
        json={'email': email, 'password': 'password123', 'full_name': 'WS User'},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data['access_token'], data['user']


def _auth(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _ws_url(session_id: int, token: str | None = None) -> str:
    if token:
        return f'/api/v1/interview/ws/{session_id}?token={token}'
    return f'/api/v1/interview/ws/{session_id}'


def _start(client: TestClient, token: str, role: str = 'Junior Java Developer') -> dict:
    resp = client.post(
        '/api/v1/interview/start',
        headers=_auth(token),
        json={'role': role, 'difficulty': 'junior'},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _recv_until(ws, expected: str, *, skip=('status',), limit: int = 5) -> dict:
    """Read WS messages until expected type (skips interim status heartbeats)."""
    last = None
    for _ in range(limit):
        last = ws.receive_json()
        if last.get('type') == expected:
            return last
        if last.get('type') in skip:
            continue
        break
    assert last is not None and last.get('type') == expected, last
    return last


def test_websocket_multi_turn_exchange(client, db_session):
    token, _user = _register(client, 'ws-multi@example.com')
    started = _start(client, token)
    session_id = started['id']

    with client.websocket_connect(_ws_url(session_id, token)) as ws:
        connected = ws.receive_json()
        assert connected['type'] == 'connected'
        assert connected['session']['id'] == session_id

        ws.send_json({'type': 'next_question'})
        q1 = _recv_until(ws, 'question')
        assert q1['question']
        assert q1['session']['current_question'] == q1['question']

        ws.send_json(
            {
                'type': 'answer',
                'answer': (
                    'An ArrayList uses a dynamic array with fast random access, while a LinkedList '
                    'is node-based. For example I prefer ArrayList for most Junior Java Developer '
                    'API lists; LinkedList only when mid-list inserts dominate. Tradeoff is locality '
                    'versus insert cost.'
                ),
            }
        )
        fb1 = _recv_until(ws, 'feedback')
        assert fb1['score'] is not None
        assert fb1['feedback']
        assert fb1['session']['running_score'] is not None

        ws.send_json({'type': 'next_question'})
        q2 = _recv_until(ws, 'question')
        assert q2['question'] != q1['question']

        ws.send_json({'type': 'answer', 'answer': 'equals and hashCode must be consistent for HashMap keys.'})
        fb2 = _recv_until(ws, 'feedback')
        assert len(fb2['session']['history']) == 2

        ws.send_json({'type': 'complete'})
        done = _recv_until(ws, 'completed')
        assert done['session']['status'] == 'completed'
        assert done['session']['in_progress'] is False


def test_websocket_reconnect_preserves_state(client, db_session):
    token, _user = _register(client, 'ws-reconnect@example.com')
    started = _start(client, token, role='Python Backend Engineer')
    session_id = started['id']

    with client.websocket_connect(_ws_url(session_id, token)) as ws:
        assert ws.receive_json()['type'] == 'connected'
        ws.send_json({'type': 'next_question'})
        q = _recv_until(ws, 'question')
        pending = q['question']

    # Reconnect â€” session state must still have the unanswered question
    with client.websocket_connect(_ws_url(session_id, token)) as ws:
        connected = ws.receive_json()
        assert connected['type'] == 'connected'
        assert connected['session']['current_question'] == pending
        assert len(connected['session']['history']) == 1
        assert connected['session']['history'][0]['answer'] is None

        ws.send_json({'type': 'get_state'})
        state_msg = _recv_until(ws, 'state')
        assert state_msg['session']['current_question'] == pending


def test_websocket_errors_are_communicated(client, db_session):
    token, _user = _register(client, 'ws-err@example.com')
    started = _start(client, token)
    session_id = started['id']

    with client.websocket_connect(_ws_url(session_id, token)) as ws:
        ws.receive_json()  # connected
        ws.send_json({'type': 'answer', 'answer': 'oops no question yet'})
        err = _recv_until(ws, 'error')
        assert err['code'] == 'no_pending_question'

        ws.send_json({'type': 'not_a_real_command'})
        err2 = _recv_until(ws, 'error')
        assert err2['code'] == 'unknown_type'

        ws.send_text('not-json')
        err3 = _recv_until(ws, 'error')
        assert err3['code'] == 'bad_message'


def test_websocket_missing_session(client):
    token, _user = _register(client, 'ws-missing@example.com')
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(99999, token)):
            pass
    assert exc.value.code == 4404


def test_websocket_rejects_missing_token(client):
    token, _user = _register(client, 'ws-notoken@example.com')
    started = _start(client, token)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(started['id'], None)):
            pass
    assert exc.value.code == 4401


def test_websocket_rejects_wrong_owner(client):
    token_a, _user_a = _register(client, 'ws-owner@example.com')
    token_b, _user_b = _register(client, 'ws-intruder@example.com')
    started = _start(client, token_a)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(_ws_url(started['id'], token_b)):
            pass
    assert exc.value.code == 4403


def test_history_persists_across_multiple_sessions(client, db_session):
    token, user = _register(client, 'hist-multi@example.com')
    headers = _auth(token)

    s1 = _start(client, token, role='Java Developer')
    s2 = _start(client, token, role='Python Developer')

    # Progress session 1
    q = client.post(f"/api/v1/interview/{s1['id']}/question", headers=headers)
    assert q.status_code == 200
    ans = client.post(
        f"/api/v1/interview/{s1['id']}/answer",
        headers=headers,
        json={
            'answer': (
                'ArrayList is array-backed with O(1) get; LinkedList is node-based. '
                'For example choose ArrayList for most Java Developer list reads.'
            )
        },
    )
    assert ans.status_code == 200
    done = client.post(
        f"/api/v1/interview/{s1['id']}/complete",
        headers=headers,
        json={'overall_feedback': 'Nice first session.'},
    )
    assert done.status_code == 200
    assert done.json()['status'] == 'completed'
    assert done.json()['overall_feedback'] == 'Nice first session.'

    # Session 2 remains independent / in progress
    assert s2['status'] == 'active'
    listed = client.get(f'/api/v1/interview/user/{user["id"]}', headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 2
    # Reverse chronological: newest first
    assert body[0]['id'] == s2['id']
    assert body[1]['id'] == s1['id']

    summary = client.get(f'/api/v1/interview/user/{user["id"]}/summary', headers=headers)
    assert summary.status_code == 200
    summaries = summary.json()
    assert summaries[0]['id'] == s2['id']
    assert summaries[1]['turn_count'] == 1
    assert summaries[1]['status'] == 'completed'

    history = client.get(f"/api/v1/interview/{s1['id']}/history", headers=headers)
    assert history.status_code == 200
    hist = history.json()
    assert hist['status'] == 'completed'
    assert len(hist['history']) == 1
    assert hist['history'][0]['answer']
    assert hist['history'][0]['score'] is not None
    assert hist['history'][0]['feedback']
    assert hist['overall_feedback'] == 'Nice first session.'

    # Completed session still readable after "end"
    again = client.get(f"/api/v1/interview/{s1['id']}", headers=headers)
    assert again.status_code == 200
    assert again.json()['history'][0]['feedback']


def test_abandon_session(client, db_session):
    token, _user = _register(client, 'abandon@example.com')
    started = _start(client, token)
    resp = client.post(f"/api/v1/interview/{started['id']}/abandon", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()['status'] == 'abandoned'
    assert resp.json()['in_progress'] is False
