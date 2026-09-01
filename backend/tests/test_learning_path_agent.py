from app.agents.learning_path_agent import (
    ROADMAP_SECTION_KEYS,
    build_learning_roadmap,
    run_learning_path_agent,
)
from app.agents.state import initial_state
from app.data.mock_resources import MOCK_RESOURCES
from app.services.faiss_store import FaissStore, reset_stores
from app.services.retrieval_service import RetrievalService, index_resources


def _retrieval(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss'))
    reset_stores()
    store = FaissStore('resources', index_dir=str(tmp_path / 'idx'))
    index_resources(store=store)
    return RetrievalService(
        jobs_store=FaissStore('jobs', index_dir=str(tmp_path / 'idx')),
        resources_store=store,
    )


def test_roadmap_has_three_sections_from_mock_gaps(tmp_path, monkeypatch):
    retrieval = _retrieval(tmp_path, monkeypatch)
    gaps = [
        {'skill': 'Kubernetes', 'priority': 'high', 'demand_pct': 80.0, 'mention_count': 4},
        {'skill': 'Docker', 'priority': 'medium', 'demand_pct': 50.0, 'mention_count': 2},
        {'skill': 'AWS', 'priority': 'low', 'demand_pct': 25.0, 'mention_count': 1},
    ]
    roadmap = build_learning_roadmap(gaps, retrieval=retrieval, profile_summary='Backend junior')
    for key in ROADMAP_SECTION_KEYS:
        assert key in roadmap
        assert roadmap[key]['skills'], f'{key} should list specific skills'
        assert roadmap[key]['resources'], f'{key} should include real resources'
        assert roadmap[key]['focus']
    reset_stores()


def test_resources_trace_to_real_urls(tmp_path, monkeypatch):
    retrieval = _retrieval(tmp_path, monkeypatch)
    known_urls = {r['url'] for r in MOCK_RESOURCES if r.get('url')}
    gaps = [
        {'skill': 'Kubernetes', 'priority': 'high', 'demand_pct': 70.0, 'mention_count': 3},
        {'skill': 'PostgreSQL', 'priority': 'medium', 'demand_pct': 40.0, 'mention_count': 2},
        {'skill': 'RAG', 'priority': 'low', 'demand_pct': 20.0, 'mention_count': 1},
    ]
    roadmap = build_learning_roadmap(gaps, retrieval=retrieval)
    all_resources = []
    for key in ROADMAP_SECTION_KEYS:
        all_resources.extend(roadmap[key]['resources'])
    assert all_resources
    allowed_hosts = (
        'fastapi.tiangolo.com',
        'openlibrary.org',
        'docs.python.org',
        'pgexercises.com',
        'redis.io',
        'kubernetes.io',
        'docs.docker.com',
        'linuxjourney.com',
        'tldp.org',
        'guides.github.com',
        'docs.github.com',
        'go.dev',
        'learncpp.com',
        'learn-c.org',
        'freecodecamp.org',
        'gaia.cs.umass.edu',
        'grpc.io',
        'oracle.com',
        'spring.io',
        'react-typescript-cheatsheet.netlify.app',
        'developer.mozilla.org',
        'sbert.net',
        'developers.google.com',
        'langchain-ai.github.io',
        'aws.amazon.com',
        'learn.microsoft.com',
        'developer.hashicorp.com',
        'graphql.org',
        'techinterviewhandbook.org',
        'owasp.org',
        'coursera.org',
        'youtube.com',
        'serpapi.com',
        'example.com',
    )
    for res in all_resources:
        assert res['url'].startswith('http')
        assert res.get('id') and res.get('skill')
        # Curated hits stay in mock corpus; API/search fallbacks use known hosts
        if res['url'] not in known_urls:
            assert any(h in res['url'] for h in allowed_hosts), res['url']
        # Never ship the known bad Open Library mix-up (Jethro Tull Heavy Horses)
        assert 'OL19748291W' not in res['url']
        assert 'Heavy_horses' not in res['url']
    reset_stores()


def test_obscure_skill_still_gets_link(tmp_path, monkeypatch):
    retrieval = _retrieval(tmp_path, monkeypatch)
    monkeypatch.setattr(
        'app.agents.learning_path_agent.SerpAPIClient.search_courses',
        lambda self, skill, num=5: [],
    )
    monkeypatch.setattr(
        'app.agents.learning_path_agent.OpenLibraryClient.search_books',
        lambda self, topic, limit=5: [],
    )
    gaps = [
        {'skill': 'Ziglang', 'priority': 'high', 'demand_pct': 10.0, 'mention_count': 1},
    ]
    roadmap = build_learning_roadmap(gaps, retrieval=retrieval)
    resources = roadmap['days_30']['resources']
    assert resources
    assert all(r.get('url', '').startswith('http') for r in resources)
    assert any('freecodecamp.org' in r['url'] or 'youtube.com' in r['url'] or 'coursera.org' in r['url'] for r in resources)
    reset_stores()


def test_mock_book_urls_point_at_matching_titles():
    books = [r for r in MOCK_RESOURCES if r.get('type') == 'book']
    assert books
    for book in books:
        assert 'OL19748291W' not in (book.get('url') or '')
        assert 'OL17869986W' not in (book.get('url') or '')  # Beginning Visual C# mix-up
    fluent = next(b for b in books if 'Fluent' in b['title'])
    ddia = next(b for b in books if 'Data-Intensive' in b['title'])
    assert 'OL19932156W' in fluent['url']
    assert 'OL19293745W' in ddia['url']


def test_openlibrary_title_match_rejects_unrelated():
    from app.clients.learning_resources import _title_matches_query

    assert _title_matches_query(
        'Designing Data-Intensive Applications',
        'data intensive applications systems',
    )
    assert _title_matches_query('Fluent Python', 'Fluent Python programming')
    assert not _title_matches_query('Heavy horses', 'system design databases')
    assert not _title_matches_query('Beginning Visual C#', 'Fluent Python')


def test_roadmap_differs_between_candidates(tmp_path, monkeypatch):
    retrieval = _retrieval(tmp_path, monkeypatch)
    backend_gaps = [
        {'skill': 'Kubernetes', 'priority': 'high', 'demand_pct': 80.0, 'mention_count': 4},
        {'skill': 'Docker', 'priority': 'medium', 'demand_pct': 50.0, 'mention_count': 2},
        {'skill': 'Terraform', 'priority': 'low', 'demand_pct': 30.0, 'mention_count': 1},
    ]
    frontend_gaps = [
        {'skill': 'React', 'priority': 'high', 'demand_pct': 90.0, 'mention_count': 5},
        {'skill': 'TypeScript', 'priority': 'medium', 'demand_pct': 60.0, 'mention_count': 3},
        {'skill': 'GraphQL', 'priority': 'low', 'demand_pct': 25.0, 'mention_count': 1},
    ]
    backend = build_learning_roadmap(backend_gaps, retrieval=retrieval, profile_summary='Backend eng')
    frontend = build_learning_roadmap(frontend_gaps, retrieval=retrieval, profile_summary='Frontend eng')

    backend_skills = {s for key in ROADMAP_SECTION_KEYS for s in backend[key]['skills']}
    frontend_skills = {s for key in ROADMAP_SECTION_KEYS for s in frontend[key]['skills']}
    assert backend_skills != frontend_skills
    assert 'Kubernetes' in backend_skills
    assert 'React' in frontend_skills
    reset_stores()


def test_run_learning_path_agent_writes_state(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss-agent'))
    reset_stores()
    index_resources()

    state = initial_state(cv_id=1)
    state['cv_summary'] = 'Python developer'
    state['skill_gaps'] = [
        {'skill': 'Kubernetes', 'priority': 'high', 'demand_pct': 75.0, 'mention_count': 3, 'reason': 'x'},
        {'skill': 'AWS', 'priority': 'medium', 'demand_pct': 40.0, 'mention_count': 2, 'reason': 'y'},
        {'skill': 'Terraform', 'priority': 'low', 'demand_pct': 20.0, 'mention_count': 1, 'reason': 'z'},
    ]
    update = run_learning_path_agent(state)
    assert update['learning_roadmap']
    for key in ROADMAP_SECTION_KEYS:
        assert update['learning_roadmap'][key]['skills']
        assert update['learning_roadmap'][key]['resources']
    assert update['node_log'][-1]['node'] == 'learning_path_agent'
    # retrieval_context is owned by Retrieval Agent (P6-10); learning path only consumes it
    assert 'retrieval_context' not in update
    reset_stores()


def test_learning_path_prefers_retrieval_context(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss-ctx'))
    reset_stores()

    state = initial_state(cv_id=1)
    state['skill_gaps'] = [
        {'skill': 'Kubernetes', 'priority': 'high', 'demand_pct': 80.0, 'mention_count': 4, 'reason': 'x'},
    ]
    state['retrieval_context'] = [
        {
            'id': 'ctx-k8s-1',
            'query': 'Kubernetes learning course',
            'requesting_agent': 'skill_gap_agent',
            'source': 'resources',
            'title': 'Kubernetes Fundamentals',
            'url': 'https://example.com/k8s',
            'text': 'Learn Kubernetes containers orchestration',
            'skill': 'Kubernetes',
            'score': 0.95,
        }
    ]
    update = run_learning_path_agent(state)
    resources = update['learning_roadmap']['days_30']['resources']
    assert any(r.get('title') == 'Kubernetes Fundamentals' for r in resources)
    assert any(r.get('url') == 'https://example.com/k8s' for r in resources)
    reset_stores()


def test_run_learning_path_agent_empty_gaps(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss-empty'))
    reset_stores()

    state = initial_state(cv_id=1)
    state['skill_gaps'] = []
    update = run_learning_path_agent(state)
    for key in ROADMAP_SECTION_KEYS:
        assert key in update['learning_roadmap']
    assert any('no skill_gaps' in w for w in update['warnings'])
    reset_stores()
