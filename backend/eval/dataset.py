"""Golden dataset loading and validation for RAG evaluation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GOLDEN_PATH = Path(__file__).with_name('golden_queries.json')

VALID_TASKS = {'market_trends', 'skill_gap', 'learning_roadmap', 'gap_narrative'}
VALID_SOURCES = {'jobs', 'resources'}
REQUIRED_FIELDS = ('id', 'query', 'task', 'sources', 'relevant_ids')


def validate_dataset(cases: Any) -> list[dict[str, Any]]:
    """Validate a golden dataset and return it (raises on malformed input)."""
    if not isinstance(cases, list) or not cases:
        raise ValueError('golden dataset must be a non-empty list')

    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError(f'golden case must be an object, got {type(case).__name__}')
        for field in REQUIRED_FIELDS:
            if field not in case:
                raise ValueError(f'case missing required field {field!r}: {case.get("id")}')
        cid = str(case['id'])
        if cid in seen:
            raise ValueError(f'duplicate case id: {cid}')
        seen.add(cid)
        if case['task'] not in VALID_TASKS:
            raise ValueError(f'case {cid}: invalid task {case["task"]!r}')
        if not isinstance(case['sources'], list) or not case['sources']:
            raise ValueError(f'case {cid}: sources must be a non-empty list')
        for source in case['sources']:
            if source not in VALID_SOURCES:
                raise ValueError(f'case {cid}: invalid source {source!r}')
        if not isinstance(case['relevant_ids'], list) or not case['relevant_ids']:
            raise ValueError(f'case {cid}: relevant_ids must be a non-empty list')
    return cases


def load_golden_dataset(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load and validate the golden dataset from JSON."""
    target = Path(path) if path else GOLDEN_PATH
    data = json.loads(target.read_text(encoding='utf-8'))
    return validate_dataset(data)
