import io
import tempfile
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.api.deps import get_db
from app.main import app
from app.services.user_service import UserService
from app.services.cv_service import CVService
from app.core.config import settings


@pytest.fixture
def engine():
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(engine):
    Sess = sessionmaker(bind=engine)
    session = Sess()
    yield session
    session.close()


@pytest.fixture
def client(engine):
    def override_get_db():
        Sess = sessionmaker(bind=engine)
        db = Sess()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_valid_pdf_bytes(text: str = 'Test CV content') -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 700), text, fontsize=12)
    bio = io.BytesIO()
    doc.save(bio)
    doc.close()
    return bio.getvalue()


def _make_txt_bytes() -> bytes:
    return b'This is a text file, not a PDF.\n'


def _register(client, email: str):
    resp = client.post(
        '/api/v1/auth/register',
        json={'email': email, 'password': 'password123', 'full_name': 'Test User'},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data['access_token'], data['user']


def _auth(token: str) -> dict:
    return {'Authorization': f'Bearer {token}'}


def _upload_pdf(client, token: str, content: bytes, content_type: str = 'application/pdf'):
    return client.post(
        '/api/v1/cv/upload',
        headers=_auth(token),
        files={'file': ('test.pdf', content, content_type)},
    )


class TestCVService:
    def test_create_cv_with_filename_and_status(self, db_session):
        user_svc = UserService(db_session)
        user = user_svc.create_user(email='ct@example.com')
        svc = CVService(db_session)
        cv = svc.create_cv(user_id=user.id, filename='abc.pdf', status='processing')
        assert cv.id is not None
        assert cv.filename == 'abc.pdf'
        assert cv.status == 'processing'

    def test_create_cv_default_status(self, db_session):
        user_svc = UserService(db_session)
        user = user_svc.create_user(email='default@example.com')
        svc = CVService(db_session)
        cv = svc.create_cv(user_id=user.id)
        assert cv.status == 'pending'

    def test_create_cv_with_raw_text_backward_compat(self, db_session):
        user_svc = UserService(db_session)
        user = user_svc.create_user(email='raw@example.com')
        svc = CVService(db_session)
        cv = svc.create_cv(user_id=user.id, raw_text='some raw text')
        assert cv.raw_text == 'some raw text'

    def test_get_cv_by_user_and_filename(self, db_session):
        user_svc = UserService(db_session)
        user = user_svc.create_user(email='fn@example.com')
        svc = CVService(db_session)
        cv = svc.create_cv(user_id=user.id, filename='unique.pdf')
        found = svc.get_cv_by_user_and_filename(user.id, 'unique.pdf')
        assert found is not None
        assert found.id == cv.id
        not_found = svc.get_cv_by_user_and_filename(user.id, 'nonexistent.pdf')
        assert not_found is None


class TestCVUploadEndpoint:
    def test_upload_pdf_creates_profile(self, client, db_session):
        token, _user = _register(client, 'upload@example.com')
        resp = _upload_pdf(client, token, _make_valid_pdf_bytes())
        assert resp.status_code == 200
        data = resp.json()
        assert data['id'] > 0
        assert data['status'] == 'completed'
        assert data['duplicate'] is False

    def test_rejects_non_pdf_content_type(self, client, db_session):
        token, _user = _register(client, 'notpdf@example.com')
        resp = _upload_pdf(client, token, _make_valid_pdf_bytes(), content_type='text/plain')
        assert resp.status_code == 415
        assert 'Only PDF files are accepted' in resp.json()['detail']

    def test_rejects_non_pdf_magic_bytes(self, client, db_session):
        token, _user = _register(client, 'badmagic@example.com')
        resp = _upload_pdf(client, token, _make_txt_bytes())
        assert resp.status_code == 415
        assert 'not a valid PDF' in resp.json()['detail']

    def test_enforces_size_limit(self, client, db_session, monkeypatch):
        monkeypatch.setattr(settings, 'cv_max_upload_size_bytes', 10)
        token, _user = _register(client, 'bigfile@example.com')
        big_pdf = b'%PDF-1.4 ' + b'x' * 1000
        resp = _upload_pdf(client, token, big_pdf)
        assert resp.status_code == 413
        assert 'exceeds maximum size' in resp.json()['detail']

    def test_duplicate_upload_returns_existing(self, client, db_session):
        token, _user = _register(client, 'dup@example.com')
        pdf = _make_valid_pdf_bytes()
        first = _upload_pdf(client, token, pdf)
        assert first.status_code == 200
        assert first.json()['duplicate'] is False
        second = _upload_pdf(client, token, pdf)
        assert second.status_code == 200
        assert second.json()['duplicate'] is True
        assert second.json()['id'] == first.json()['id']

    def test_file_stored_on_disk(self, client, db_session, tmp_path, monkeypatch):
        upload_dir = tmp_path / 'uploads' / 'cv'
        upload_dir.mkdir(parents=True)
        token, _user = _register(client, 'disk@example.com')
        monkeypatch.setattr(settings, 'cv_upload_dir', str(upload_dir))
        pdf_bytes = _make_valid_pdf_bytes()
        resp = _upload_pdf(client, token, pdf_bytes)
        assert resp.status_code == 200
        stored_files = list(upload_dir.glob('*.pdf'))
        assert len(stored_files) == 1
        assert stored_files[0].name.endswith('.pdf')
        assert stored_files[0].read_bytes() == pdf_bytes

    def test_get_cv_returns_status_and_filename(self, client, db_session):
        token, _user = _register(client, 'getcv@example.com')
        resp = _upload_pdf(client, token, _make_valid_pdf_bytes())
        cv_id = resp.json()['id']
        get_resp = client.get(f'/api/v1/cv/{cv_id}', headers=_auth(token))
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data['status'] == 'completed'
        assert data['filename'] is not None
        assert data['filename'].endswith('.pdf')

    def test_get_nonexistent_cv_returns_404(self, client):
        token, _user = _register(client, 'missing@example.com')
        resp = client.get('/api/v1/cv/99999', headers=_auth(token))
        assert resp.status_code == 404

    def test_extraction_failure_sets_status_failed(self, client, db_session, tmp_path, monkeypatch):
        upload_dir = tmp_path / 'uploads' / 'cv'
        upload_dir.mkdir(parents=True)
        monkeypatch.setattr(settings, 'cv_upload_dir', str(upload_dir))
        token, _user = _register(client, 'badcv@example.com')
        resp = _upload_pdf(client, token, b'%PDF-1.4 corrupted garbage')
        assert resp.status_code == 422
        assert 'extraction failed' in resp.json()['detail']

    def test_empty_pdf_sets_status_failed(self, client, db_session, tmp_path, monkeypatch):
        upload_dir = tmp_path / 'uploads' / 'cv'
        upload_dir.mkdir(parents=True)
        monkeypatch.setattr(settings, 'cv_upload_dir', str(upload_dir))
        token, _user = _register(client, 'emptypdf@example.com')
        doc = fitz.open()
        doc.new_page(width=612, height=792)
        bio = io.BytesIO()
        doc.save(bio)
        doc.close()
        resp = _upload_pdf(client, token, bio.getvalue())
        assert resp.status_code == 422
        assert 'extraction failed' in resp.json()['detail']

    def test_upload_stores_raw_text(self, client, db_session, tmp_path, monkeypatch):
        upload_dir = tmp_path / 'uploads' / 'cv'
        upload_dir.mkdir(parents=True)
        monkeypatch.setattr(settings, 'cv_upload_dir', str(upload_dir))
        token, _user = _register(client, 'rawtext@example.com')
        resp = _upload_pdf(client, token, _make_valid_pdf_bytes('Skills: Python, SQL'))
        assert resp.status_code == 200
        cv_id = resp.json()['id']
        get_resp = client.get(f'/api/v1/cv/{cv_id}', headers=_auth(token))
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data['raw_text'] is not None
        assert 'Python' in data['raw_text']
        assert data['status'] == 'completed'
