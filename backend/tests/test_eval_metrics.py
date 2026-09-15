"""Deterministic retrieval metric tests."""

from eval.metrics import document_key, document_keys, mrr, precision_at_k, recall_at_k


def test_precision_at_k():
    retrieved = ['a', 'b', 'c', 'd']
    relevant = {'b', 'x'}
    assert precision_at_k(retrieved, relevant, 3) == 1 / 3
    assert precision_at_k(retrieved, relevant, 1) == 0.0
    assert precision_at_k([], relevant, 5) == 0.0


def test_recall_at_k():
    retrieved = ['a', 'b', 'c']
    relevant = {'b', 'z', 'w'}
    assert recall_at_k(retrieved, relevant, 5) == 1 / 3
    assert recall_at_k(retrieved, set(), 5) == 0.0
    assert recall_at_k(retrieved, {'a', 'b'}, 1) == 1 / 2


def test_mrr():
    assert mrr(['a', 'b', 'c'], {'c'}) == 1 / 3
    assert mrr(['a', 'b', 'c'], {'a'}) == 1.0
    assert mrr(['a', 'b', 'c'], {'z'}) == 0.0


def test_document_key_strips_chunk_suffix():
    item = {'id': 'res-docker-k8s#0', 'source': 'resources', 'doc_id': 'res-docker-k8s'}
    assert document_key(item) == 'res-docker-k8s'


def test_document_key_jobs_uses_external_id():
    item = {'id': '3', 'source': 'jobs', 'metadata': {'external_id': 'eval-backend'}}
    assert document_key(item) == 'eval-backend'


def test_document_keys_mixed_sources():
    items = [
        {'id': 'res-x#0', 'source': 'resources', 'doc_id': 'res-x'},
        {'id': '7', 'source': 'jobs', 'metadata': {'external_id': 'eval-y'}},
    ]
    assert document_keys(items) == ['res-x', 'eval-y']
