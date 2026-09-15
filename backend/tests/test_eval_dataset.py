"""Golden dataset loading/validation tests."""

import pytest

from eval.dataset import load_golden_dataset, validate_dataset


def test_default_dataset_loads_and_validates():
    cases = load_golden_dataset()
    assert 15 <= len(cases) <= 25
    ids = {c['id'] for c in cases}
    assert 'k8s-learn' in ids
    assert 'jobs-backend' in ids


def test_valid_case_accepted():
    cases = validate_dataset(
        [{'id': 'a', 'query': 'q', 'task': 'gap_narrative', 'sources': ['resources'], 'relevant_ids': ['res-x']}]
    )
    assert cases[0]['id'] == 'a'


@pytest.mark.parametrize(
    'case',
    [
        {'query': 'q', 'task': 'gap_narrative', 'sources': ['resources'], 'relevant_ids': ['r']},
        {'id': 'a', 'task': 'gap_narrative', 'sources': ['resources'], 'relevant_ids': ['r']},
        {'id': 'a', 'query': 'q', 'task': 'gap_narrative', 'sources': [], 'relevant_ids': ['r']},
        {'id': 'a', 'query': 'q', 'task': 'gap_narrative', 'sources': ['resources'], 'relevant_ids': []},
        {'id': 'a', 'query': 'q', 'task': 'not_a_task', 'sources': ['resources'], 'relevant_ids': ['r']},
        {'id': 'a', 'query': 'q', 'task': 'gap_narrative', 'sources': ['bogus'], 'relevant_ids': ['r']},
    ],
)
def test_invalid_case_rejected(case):
    with pytest.raises(ValueError):
        validate_dataset([case])


def test_duplicate_id_rejected():
    base = {'query': 'q', 'task': 'gap_narrative', 'sources': ['resources'], 'relevant_ids': ['r']}
    with pytest.raises(ValueError):
        validate_dataset([{**base, 'id': 'dup'}, {**base, 'id': 'dup'}])


def test_empty_dataset_rejected():
    with pytest.raises(ValueError):
        validate_dataset([])
