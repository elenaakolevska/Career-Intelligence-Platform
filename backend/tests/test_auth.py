"""Auth register/login/me and CV ownership scoping."""

from __future__ import annotations

import io

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
def client(engine):
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register(client: TestClient, email: str = 'alice@example.com', password: str = 'password123'):
    resp = client.post(
        '/api/v1/auth/register',
        json={'email': email, 'password': password, 'full_name': 'Alice'},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data['access_token'], data['user']


def _auth(token: str) -> dict[str, str]:
    return {'Authorization': f'Bearer {token}'}


def _pdf_bytes(text: str = 'Skills: Python') -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 700), text, fontsize=12)
    bio = io.BytesIO()
    doc.save(bio)
    doc.close()
    return bio.getvalue()


def test_register_login_me(client):
    token, user = _register(client)
    assert user['email'] == 'alice@example.com'
    assert user['id'] > 0

    me = client.get('/api/v1/auth/me', headers=_auth(token))
    assert me.status_code == 200
    assert me.json()['id'] == user['id']

    login = client.post(
        '/api/v1/auth/login',
        json={'email': 'alice@example.com', 'password': 'password123'},
    )
    assert login.status_code == 200
    assert login.json()['user']['id'] == user['id']
    assert login.json()['access_token']


def test_login_rejects_bad_password(client):
    _register(client)
    resp = client.post(
        '/api/v1/auth/login',
        json={'email': 'alice@example.com', 'password': 'wrong-password'},
    )
    assert resp.status_code == 401


def test_login_request_allows_short_password():
    """LoginRequest must not impose a min-length the frontend doesn't enforce.

    Regression guard: a login attempt with a short password must be accepted by
    the request schema (the real check is password correctness, not length).
    """
    from app.schemas.auth import LoginRequest

    request = LoginRequest(email='alice@example.com', password='x')
    assert request.password == 'x'


def test_me_requires_auth(client):
    resp = client.get('/api/v1/auth/me')
    assert resp.status_code == 401


def test_cv_list_scoped_to_owner(client, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'cv_upload_dir', str(tmp_path))
    monkeypatch.setattr(settings, 'enable_cv_llm_parse', False)
    monkeypatch.setattr(settings, 'enable_auto_embed', False)

    token_a, user_a = _register(client, email='a-owner@example.com')
    token_b, _user_b = _register(client, email='b-other@example.com')

    up = client.post(
        '/api/v1/cv/upload',
        headers=_auth(token_a),
        files={'file': ('cv.pdf', _pdf_bytes(), 'application/pdf')},
    )
    assert up.status_code == 200, up.text
    cv_id = up.json()['id']

    mine = client.get('/api/v1/cv/', headers=_auth(token_a))
    assert mine.status_code == 200
    assert len(mine.json()) == 1
    assert mine.json()[0]['id'] == cv_id
    assert mine.json()[0]['user_id'] == user_a['id']

    other = client.get('/api/v1/cv/', headers=_auth(token_b))
    assert other.status_code == 200
    assert other.json() == []

    forbidden = client.get(f'/api/v1/cv/{cv_id}', headers=_auth(token_b))
    assert forbidden.status_code == 403


def test_spoofed_user_id_on_upload_rejected(client, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'cv_upload_dir', str(tmp_path))
    monkeypatch.setattr(settings, 'enable_cv_llm_parse', False)
    monkeypatch.setattr(settings, 'enable_auto_embed', False)

    token_a, user_a = _register(client, email='owner@example.com')
    _token_b, user_b = _register(client, email='attacker@example.com')

    resp = client.post(
        '/api/v1/cv/upload',
        headers=_auth(token_a),
        data={'user_id': str(user_b['id'])},
        files={'file': ('cv.pdf', _pdf_bytes(), 'application/pdf')},
    )
    assert resp.status_code == 403
    # Upload as self still works
    ok = client.post(
        '/api/v1/cv/upload',
        headers=_auth(token_a),
        data={'user_id': str(user_a['id'])},
        files={'file': ('cv2.pdf', _pdf_bytes('Java FastAPI'), 'application/pdf')},
    )
    assert ok.status_code == 200


def test_update_profile(client):
    token, user = _register(client)

    resp = client.patch(
        '/api/v1/users/me',
        headers=_auth(token),
        json={'full_name': 'Alice Updated', 'email': 'alice.new@example.com'},
    )
    assert resp.status_code == 200
    assert resp.json()['full_name'] == 'Alice Updated'
    assert resp.json()['email'] == 'alice.new@example.com'
    assert resp.json()['id'] == user['id']

    me = client.get('/api/v1/auth/me', headers=_auth(token))
    assert me.json()['email'] == 'alice.new@example.com'


def test_update_email_conflict_rejected(client):
    token, _user = _register(client, email='first@example.com')
    _token2, _user2 = _register(client, email='second@example.com')

    resp = client.patch(
        '/api/v1/users/me',
        headers=_auth(token),
        json={'email': 'second@example.com'},
    )
    assert resp.status_code == 422


def test_change_password_roundtrip(client):
    token, _user = _register(client)

    resp = client.post(
        '/api/v1/users/me/password',
        headers=_auth(token),
        json={'current_password': 'password123', 'new_password': 'newpassword99'},
    )
    assert resp.status_code == 200, resp.text

    old = client.post(
        '/api/v1/auth/login',
        json={'email': 'alice@example.com', 'password': 'password123'},
    )
    assert old.status_code == 401
    new = client.post(
        '/api/v1/auth/login',
        json={'email': 'alice@example.com', 'password': 'newpassword99'},
    )
    assert new.status_code == 200


def test_change_password_rejects_wrong_current(client):
    token, _user = _register(client)

    resp = client.post(
        '/api/v1/users/me/password',
        headers=_auth(token),
        json={'current_password': 'wrong', 'new_password': 'newpassword99'},
    )
    assert resp.status_code == 422


def test_protected_endpoints_reject_unauthenticated(client):
    assert client.get('/api/v1/users/1').status_code == 401
    assert client.post('/api/v1/users/', json={'email': 'anon@example.com'}).status_code == 401
    assert (
        client.post(
            '/api/v1/rag/generate',
            json={'query': 'python jobs', 'task': 'skill_gap'},
        ).status_code
        == 401
    )
    assert client.get('/api/v1/rag/tasks').status_code == 401
    assert client.get('/api/v1/retrieval/', params={'q': 'python'}).status_code == 401
    assert client.post('/api/v1/retrieval/resources/reindex').status_code == 401


def test_user_profile_scoped_to_self(client):
    token_a, user_a = _register(client, email='self-a@example.com')
    token_b, user_b = _register(client, email='self-b@example.com')

    own = client.get(f'/api/v1/users/{user_a["id"]}', headers=_auth(token_a))
    assert own.status_code == 200
    assert own.json()['id'] == user_a['id']

    other = client.get(f'/api/v1/users/{user_a["id"]}', headers=_auth(token_b))
    assert other.status_code == 403
    assert user_b['id'] != user_a['id']
