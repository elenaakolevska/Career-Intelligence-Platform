"""RAG index migration verification (whole-document → chunk-level resources)."""

import pytest

from app.services.embedding_service import embed
from app.services.faiss_store import FaissStore, reset_stores
from app.services.retrieval_service import RetrievalService, ensure_resource_index


@pytest.fixture(autouse=True)
def _stub(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    reset_stores()
    yield
    reset_stores()


def test_legacy_whole_doc_index_is_detected_and_rebuilt(tmp_path):
    store = FaissStore('resources', index_dir=str(tmp_path / 'idx'))
    # Simulate the pre-3A whole-document index (doc ids, no chunk suffix).
    store.add('res-python-fastapi', embed('FastAPI tutorial')[0])
    store.add('res-docker-k8s', embed('Kubernetes basics')[0])
    assert store.size == 2
    assert 'res-python-fastapi' in set(store._ids)

    ensure_resource_index(store=store)

    ids = set(store._ids)
    assert 'res-python-fastapi' not in ids  # legacy whole-doc key removed
    assert 'res-python-fastapi#0' in ids  # chunk key present
    assert all('#' in chunk_id for chunk_id in ids)  # all keys are chunk keys
    assert len(ids) == store.size  # no duplicates


def test_retrieval_returns_chunk_level_metadata(tmp_path):
    store = FaissStore('resources', index_dir=str(tmp_path / 'idx'))
    ensure_resource_index(store=store)

    jobs = FaissStore('jobs', index_dir=str(tmp_path / 'idx2'))
    svc = RetrievalService(db=None, jobs_store=jobs, resources_store=store)
    result = svc.retrieve('Kubernetes Docker containers', top_k=3, sources=['resources'])

    assert result.items
    for item in result.items:
        assert item.source == 'resources'
        assert item.doc_id
        assert item.chunk_id
        assert '#' in item.chunk_id  # chunk-level id
        assert item.doc_id in item.chunk_id  # chunk id is derived from doc id


def test_index_resources_produces_chunk_keys(tmp_path):
    store = FaissStore('resources', index_dir=str(tmp_path / 'idx'))
    ensure_resource_index(store=store)
    assert all('#' in chunk_id for chunk_id in store._ids)
    assert len(store._ids) >= 20  # full curated corpus is indexed as chunks
