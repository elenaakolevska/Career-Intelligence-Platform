"""Report provenance tests: citations validated against retrieved context."""

from app.agents.report_agent import build_final_report
from app.agents.state import initial_state


def _narrative(*, citations, context_items):
    return {
        'skill': 'Kubernetes',
        'priority': 'high',
        'task': 'gap_narrative',
        'answer': 'Grounded in CONTEXT.',
        'grounded': True,
        'empty_context': False,
        'citations': citations,
        'context_items': context_items,
    }


def _context_items():
    return [
        {
            'id': 'res-docker-k8s#0',
            'source': 'resources',
            'doc_id': 'res-docker-k8s',
            'chunk_id': 'res-docker-k8s#0',
            'score': 0.5,
            'title': 'Kubernetes Basics',
            'url': 'https://kubernetes.io/docs/tutorials/kubernetes-basics/',
        },
        {
            'id': '1',
            'source': 'jobs',
            'doc_id': '1',
            'chunk_id': '1',
            'score': 0.4,
            'title': 'Backend Engineer',
            'url': 'https://example.com/job/1',
        },
    ]


def test_valid_citations_are_preserved():
    state = initial_state(cv_id=1)
    state['retrieval_narratives'] = [
        _narrative(
            citations=['resources:res-docker-k8s#0', 'jobs:1'],
            context_items=_context_items(),
        )
    ]
    report = build_final_report(state)
    insight = report['insights'][0]
    assert insight['citations'] == ['resources:res-docker-k8s', 'jobs:1']
    assert len(insight['sources']) == 2


def test_invalid_citations_are_rejected():
    state = initial_state(cv_id=1)
    state['retrieval_narratives'] = [
        _narrative(
            citations=['resources:res-docker-k8s#0', 'resources:res-fake#0', 'jobs:999'],
            context_items=_context_items(),
        )
    ]
    report = build_final_report(state)
    insight = report['insights'][0]
    assert insight['citations'] == ['resources:res-docker-k8s']
    refs = {s['ref'] for s in report['sources']}
    assert 'resources:res-docker-k8s' in refs
    assert 'resources:res-fake' not in refs
    assert 'jobs:999' not in refs


def test_duplicate_sources_are_deduplicated():
    state = initial_state(cv_id=1)
    state['retrieval_narratives'] = [
        _narrative(citations=['resources:res-docker-k8s#0'], context_items=_context_items()),
        _narrative(citations=['resources:res-docker-k8s#0', 'jobs:1'], context_items=_context_items()),
    ]
    report = build_final_report(state)
    refs = [s['ref'] for s in report['sources']]
    assert refs.count('resources:res-docker-k8s') == 1
    assert refs.count('jobs:1') == 1
    assert len(report['sources']) == 2


def test_final_report_contains_provenance_fields():
    state = initial_state(cv_id=1)
    state['retrieval_narratives'] = [
        _narrative(citations=['jobs:1'], context_items=_context_items())
    ]
    report = build_final_report(state)
    assert 'sources' in report
    assert 'insights' in report
    assert isinstance(report['sources'], list)
    assert isinstance(report['insights'], list)
    assert report['sources'][0]['url'] == 'https://example.com/job/1'


def test_report_without_rag_data_still_works():
    state = initial_state(cv_id=1)
    state['cv_summary'] = 'Sparse profile'
    report = build_final_report(state)
    assert report['sources'] == []
    assert report['insights'] == []
    assert 'cv_summary' in report
    assert 'ats' in report['missing_sections']
