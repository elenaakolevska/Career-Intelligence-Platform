from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app import models
from app.services.embedding_service import embed
from app.services.faiss_store import FaissStore, reset_stores
from app.services.retrieval_service import RetrievalService, index_resources, retrieve


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


@pytest.fixture
def isolated_stores(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    reset_stores()
    jobs = FaissStore('jobs', index_dir=str(tmp_path / 'idx'))
    resources = FaissStore('resources', index_dir=str(tmp_path / 'idx'))
    yield jobs, resources
    reset_stores()


def test_retrieve_across_jobs_and_resources(db_session, isolated_stores):
    jobs_store, resources_store = isolated_stores

    job = models.JobPosting(
        title='Backend Engineer FastAPI',
        company='Acme',
        location='London',
        description='Python FastAPI PostgreSQL REST APIs',
        url='https://example.com/j/1',
        external_id='t1',
        source='mock',
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    jobs_store.add(str(job.id), embed('Python FastAPI backend PostgreSQL')[0])
    index_resources(store=resources_store)

    result = RetrievalService(
        db_session, jobs_store=jobs_store, resources_store=resources_store
    ).retrieve('Python FastAPI backend APIs', top_k=5)

    assert result.query.startswith('Python')
    assert set(result.sources) >= {'jobs', 'resources'}
    assert result.items
    assert result.latency_ms >= 0
    assert result.latency_ms < 2000  # interactive budget for stub embeddings
    sources_seen = {item.source for item in result.items}
    assert 'jobs' in sources_seen or 'resources' in sources_seen
    for item in result.items:
        assert item.id
        assert item.source in {'jobs', 'resources'}
        assert item.text
        assert 'entity_id' in item.metadata or 'job_id' in item.metadata or 'url' in item.metadata


def test_retrieve_single_source_resources(isolated_stores):
    _jobs_store, resources_store = isolated_stores
    index_resources(store=resources_store)
    result = RetrievalService(
        jobs_store=_jobs_store, resources_store=resources_store
    ).retrieve('Kubernetes Docker containers', top_k=3, sources=['resources'])
    assert result.sources == ['resources']
    assert all(item.source == 'resources' for item in result.items)
    assert any('Kubernetes' in (item.title or '') or 'Kubernetes' in item.text for item in result.items)


def test_retrieve_empty_query(isolated_stores):
    jobs_store, resources_store = isolated_stores
    result = RetrievalService(jobs_store=jobs_store, resources_store=resources_store).retrieve('   ')
    assert result.empty is True
    assert result.items == []


def test_module_level_retrieve_wrapper(isolated_stores):
    _jobs, resources_store = isolated_stores
    index_resources(store=resources_store)
    # Use service directly with stores; module wrapper uses global stores — seed globals via reset+index
    reset_stores()
    from app.core.config import settings
    from app.services.faiss_store import get_store

    # Point global store at temp dir by indexing through get_store after monkeypatch of faiss dir
    # Already monkeypatched embedding; set faiss dir via re-get with index_dir through index_resources on global
    store = get_store('resources', index_dir=str(Path(resources_store.root)))
    index_resources(store=store)
    result = retrieve('sentence transformers embeddings NLP', top_k=3, sources=['resources'])
    assert isinstance(result.latency_ms, float)
    assert result.items
