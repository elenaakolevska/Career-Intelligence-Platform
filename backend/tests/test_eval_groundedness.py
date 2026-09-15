"""Deterministic groundedness tests (no LLM required)."""

from eval.groundedness import deterministic_groundedness, is_hedge


def _items():
    return [
        {'id': 'res-x#0', 'source': 'resources', 'doc_id': 'res-x', 'chunk_id': 'res-x#0', 'url': 'https://x'}
    ]


def test_is_hedge_detects_markers():
    assert is_hedge('Insufficient retrieved context to explain this gap.')
    assert not is_hedge('Here is a real explanation.')


def test_empty_context_hedge_is_grounded():
    result = deterministic_groundedness(
        'Insufficient retrieved context to explain this gap.',
        [],
        empty_context=True,
    )
    assert result['grounded'] is True
    assert result['empty_context'] is True


def test_empty_context_confident_answer_not_grounded():
    result = deterministic_groundedness(
        'You should definitely learn Kubernetes.',
        [],
        empty_context=True,
    )
    assert result['grounded'] is False


def test_cited_answer_is_grounded():
    result = deterministic_groundedness(
        'This is relevant ([resources:res-x#0]).',
        _items(),
        empty_context=False,
    )
    assert result['grounded'] is True


def test_hallucinated_citation_not_grounded():
    result = deterministic_groundedness(
        'This is relevant ([resources:res-fake#0]).',
        _items(),
        empty_context=False,
    )
    assert result['grounded'] is False
    assert result['invalid_citations'] == 1


def test_empty_answer_not_grounded():
    result = deterministic_groundedness('', _items(), empty_context=False)
    assert result['grounded'] is False
