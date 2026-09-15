"""Citation correctness tests (reuse the production validation system)."""

from app.schemas.retrieval import RetrievedItem
from eval.citation import evaluate_citations


def _dict_items():
    return [
        {
            'id': 'res-docker-k8s#0',
            'source': 'resources',
            'doc_id': 'res-docker-k8s',
            'chunk_id': 'res-docker-k8s#0',
            'title': 'Kubernetes Basics',
            'url': 'https://kubernetes.io/',
        },
        {
            'id': '1',
            'source': 'jobs',
            'doc_id': '1',
            'chunk_id': '1',
            'title': 'Backend Engineer',
            'url': None,
        },
    ]


def test_valid_citations_reported():
    answer = 'Learn this ([resources:res-docker-k8s#0]) and ([jobs:1]).'
    result = evaluate_citations(answer, _dict_items())
    assert result['invalid'] == []
    assert set(result['valid']) == {'resources:res-docker-k8s', 'jobs:1'}
    assert result['accuracy'] == 1.0


def test_invalid_citation_detected():
    answer = 'See ([resources:res-fake#0]) and ([jobs:999]).'
    result = evaluate_citations(answer, _dict_items())
    assert set(result['invalid']) == {'resources:res-fake#0', 'jobs:999'}
    assert result['valid'] == []
    assert result['accuracy'] == 0.0


def test_accuracy_counts_mixed():
    answer = 'Good ([resources:res-docker-k8s#0]), bad ([jobs:42]).'
    result = evaluate_citations(answer, _dict_items())
    assert result['valid'] == ['resources:res-docker-k8s']
    assert result['invalid'] == ['jobs:42']
    assert result['accuracy'] == 0.5


def test_no_citations_accuracy_none():
    result = evaluate_citations('no citations here', _dict_items())
    assert result['valid'] == []
    assert result['invalid'] == []
    assert result['accuracy'] is None


def test_accepts_retrieved_item_objects():
    items = [
        RetrievedItem(
            id='res-x#0',
            source='resources',
            score=0.5,
            title='X',
            text='x',
            doc_id='res-x',
            chunk_id='res-x#0',
            metadata={'url': 'https://x'},
        )
    ]
    result = evaluate_citations('([resources:res-x#0])', items)
    assert result['valid'] == ['resources:res-x']
    assert result['invalid'] == []
