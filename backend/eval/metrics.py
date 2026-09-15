"""Pure, deterministic retrieval metrics (no model/provider dependency).

Relevance is defined at the *document* level:

- resources → a retrieved chunk is relevant when its ``doc_id`` (e.g.
  ``res-docker-k8s``, obtained by stripping the ``#N`` chunk suffix) is in the
  golden ``relevant_ids`` set.
- jobs → a retrieved job is relevant when its ``metadata.external_id`` is in
  the golden ``relevant_ids`` set.
"""

from __future__ import annotations

from typing import Any, Sequence


def precision_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of the top-k retrieved items that are relevant."""
    top = list(retrieved[:k])
    if not top:
        return 0.0
    return sum(1 for r in top if r in relevant) / len(top)


def recall_at_k(retrieved: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of the relevant items found in the top-k retrieved items."""
    if not relevant:
        return 0.0
    top = list(retrieved[:k])
    return sum(1 for r in top if r in relevant) / len(relevant)


def mrr(retrieved: Sequence[str], relevant: set[str]) -> float:
    """Mean reciprocal rank of the first relevant item (single-query form)."""
    for rank, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def document_key(item: dict[str, Any]) -> str:
    """Return the relevance key for a single retrieved item (dict form)."""
    source = item.get('source')
    if source == 'jobs':
        return str((item.get('metadata') or {}).get('external_id') or item.get('id') or '')
    return str(item.get('doc_id') or item.get('id') or '')


def document_keys(items: Sequence[dict[str, Any]]) -> list[str]:
    """Map retrieved items to their relevance keys (document level)."""
    return [document_key(item) for item in items]
