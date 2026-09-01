from pathlib import Path

import numpy as np

from app.data.mock_jobs import MOCK_JOBS
from app.services.embedding_service import cosine_similarity, embed
from app.services.faiss_store import FaissStore, reset_stores
from app.services.job_normalizer import normalize_adzuna_job
from app.services.job_query_builder import build_job_query


def test_embed_similar_sentences_score_higher(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    a = embed('Python FastAPI backend engineer PostgreSQL')[0]
    b = embed('Python FastAPI backend developer SQL database')[0]
    c = embed('professional chef pastry baking recipes')[0]
    assert cosine_similarity(a, b) > cosine_similarity(a, c)


def test_faiss_add_reload_search(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    reset_stores()
    store = FaissStore('jobs_test', index_dir=str(tmp_path))
    v1 = embed('python fastapi backend api postgresql')[0]
    v2 = embed('watercolor painting gallery exhibition')[0]
    store.add('1', v1)
    store.add('2', v2)
    reset_stores()
    reloaded = FaissStore('jobs_test', index_dir=str(tmp_path))
    hits = reloaded.search(embed('python fastapi backend')[0], top_k=2)
    assert hits
    assert hits[0][0] == '1'
    assert reloaded.size == 2


def test_job_query_builder_varies_by_profile():
    q1 = build_job_query({'skills': ['Python', 'FastAPI'], 'experience': [{'title': 'Backend Engineer'}], 'location': 'London'})
    q2 = build_job_query({'skills': ['React', 'TypeScript'], 'experience': [{'title': 'Frontend Engineer'}], 'location': 'Berlin'})
    q3 = build_job_query({})
    assert q1['what'] != q2['what']
    assert 'software engineer' in q3['what'].lower()
    assert q1['where'] == 'London'
    # Non-UK locations are omitted for the default GB Adzuna market
    assert q2['where'] == ''


def test_job_query_builder_skips_project_titles_and_mk_location():
    q = build_job_query(
        {
            'skills': ['Python', 'Java', 'React'],
            'experience': [{'title': 'Student Connect Project'}],
            'location': 'Ohrid, North Macedonia',
        }
    )
    assert 'Student Connect' not in q['what']
    assert 'Python' in q['what']
    assert q['where'] == ''


def test_normalize_adzuna_job_handles_missing_fields():
    normalized = normalize_adzuna_job(
        {
            'id': 99,
            'title': 'Engineer',
            'company': {'display_name': 'Acme'},
            'location': {'display_name': 'UK'},
            'description': 'Build things',
            'redirect_url': 'https://example.com/j/99',
        }
    )
    assert normalized['title'] == 'Engineer'
    assert normalized['company'] == 'Acme'
    assert normalized['external_id'] == '99'
    sparse = normalize_adzuna_job({'title': 'X'})
    assert sparse['company'] is None
    assert sparse['title'] == 'X'


def test_mock_jobs_dataset_size():
    assert len(MOCK_JOBS) >= 30
    for job in MOCK_JOBS:
        assert 'title' in job and 'external_id' in job


def test_mk_mock_corpus_and_profile_selection():
    from app.data.mock_jobs import MK_MOCK_JOBS, cv_prefers_macedonia_market, select_mock_jobs_for_profile

    assert len(MK_MOCK_JOBS) >= 12
    assert any('Skopje' in (j.get('location') or '') for j in MK_MOCK_JOBS)
    assert any('Spring Boot' in (j.get('description') or '') for j in MK_MOCK_JOBS)

    mk_profile = {'location': 'Ohrid, North Macedonia', 'skills': ['Java', 'React']}
    uk_profile = {'location': 'London, UK', 'skills': ['Python']}
    assert cv_prefers_macedonia_market(mk_profile) is True
    assert cv_prefers_macedonia_market(uk_profile) is False

    mk_jobs = select_mock_jobs_for_profile(mk_profile, limit=10)
    assert all('Macedonia' in (j.get('location') or '') or j.get('source') == 'mock-mk' for j in mk_jobs[:5])
    uk_jobs = select_mock_jobs_for_profile(uk_profile, limit=5)
    assert all(j.get('source') != 'mock-mk' for j in uk_jobs)
