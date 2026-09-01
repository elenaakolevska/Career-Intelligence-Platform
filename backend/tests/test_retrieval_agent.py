from app.agents.retrieval_agent import build_retrieval_requests, run_retrieval_agent
from app.agents.state import initial_state
from app.services.faiss_store import FaissStore, reset_stores
from app.services.retrieval_service import RetrievalService, index_resources


def test_retrieval_agent_populates_context_from_mock_request(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss'))
    reset_stores()
    store = FaissStore('resources', index_dir=str(tmp_path / 'idx'))
    index_resources(store=store)

    state = initial_state(cv_id=1)
    state['retrieval_requests'] = [
        {
            'query': 'Kubernetes Docker containers course',
            'requesting_agent': 'skill_gap_agent',
            'sources': ['resources'],
            'top_k': 3,
            'skill': 'Kubernetes',
        }
    ]
    # Patch RetrievalService used inside agent to use our store
    import app.agents.retrieval_agent as ra

    original = ra.RetrievalService

    def _factory(db=None):
        return RetrievalService(
            db,
            jobs_store=FaissStore('jobs', index_dir=str(tmp_path / 'idx')),
            resources_store=store,
        )

    monkeypatch.setattr(ra, 'RetrievalService', _factory)
    update = run_retrieval_agent(state)
    assert update['retrieval_context']
    for item in update['retrieval_context']:
        assert item.get('query')
        assert item.get('requesting_agent') == 'skill_gap_agent'
        assert item.get('id')
        assert item.get('source')
    assert update.get('retrieval_requests') == []
    assert update['node_log'][-1]['node'] == 'retrieval_agent'
    monkeypatch.setattr(ra, 'RetrievalService', original)
    reset_stores()


def test_build_requests_from_skill_gaps():
    state = initial_state(cv_id=1)
    state['skill_gaps'] = [
        {'skill': 'Kubernetes', 'priority': 'high'},
        {'skill': 'AWS', 'priority': 'medium'},
    ]
    reqs = build_retrieval_requests(state)
    assert any('Kubernetes' in r['query'] for r in reqs)
    assert all(r.get('requesting_agent') for r in reqs)
