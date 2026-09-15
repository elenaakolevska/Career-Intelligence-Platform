"""Shared citation validation for RAG provenance.

Used by the production report flow (``report_agent``) and by the RAG
evaluation harness, so there is exactly one validation system.

A citation ref is ``source:id`` (e.g. ``resources:res-docker-k8s#0`` or
``jobs:1``). It is valid only when it maps to an item that was actually
retrieved. Chunk-level ids (``res-x#0``) are accepted and canonicalized to
their document ref (``source:doc_id``).
"""

from __future__ import annotations

from typing import Any, Sequence


def _normalize_item(item: Any) -> dict[str, Any]:
    """Normalize a narrative context item (dict or RetrievedItem) to common keys."""
    if isinstance(item, dict):
        return {
            'id': item.get('id'),
            'source': item.get('source'),
            'doc_id': item.get('doc_id'),
            'chunk_id': item.get('chunk_id'),
            'title': item.get('title'),
            'url': item.get('url'),
        }
    meta = getattr(item, 'metadata', None) or {}
    return {
        'id': getattr(item, 'id', None),
        'source': getattr(item, 'source', None),
        'doc_id': getattr(item, 'doc_id', None),
        'chunk_id': getattr(item, 'chunk_id', None),
        'title': getattr(item, 'title', None),
        'url': meta.get('url') if isinstance(meta, dict) else None,
    }


def build_anchor_map(context_items: Sequence[Any]) -> dict[str, dict[str, Any]]:
    """Map every ``source:id`` / ``source:doc_id`` anchor to a canonical source dict."""
    anchors: dict[str, dict[str, Any]] = {}
    for raw in context_items or []:
        item = _normalize_item(raw)
        source = item.get('source')
        doc_id = item.get('doc_id') or item.get('id')
        if not source:
            continue
        canonical = {
            'ref': f'{source}:{doc_id}',
            'source': source,
            'title': item.get('title'),
            'url': item.get('url'),
        }
        for anchor in {item.get('id'), item.get('doc_id'), doc_id}:
            if anchor:
                anchors[f'{source}:{anchor}'] = canonical
    return anchors


def validate_citations(
    citations: Sequence[str] | None,
    context_items: Sequence[Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate citation refs against retrieved context.

    Returns ``(valid, invalid)`` where ``valid`` is a deduplicated list of
    canonical source dicts and ``invalid`` is the list of refs that do not
    map to any retrieved item.
    """
    anchors = build_anchor_map(context_items)
    valid: list[dict[str, Any]] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for ref in citations or []:
        canonical = anchors.get(ref)
        if canonical is None:
            invalid.append(ref)
        elif canonical['ref'] not in seen:
            seen.add(canonical['ref'])
            valid.append(canonical)
    return valid, invalid
