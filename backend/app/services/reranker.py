"""Lightweight reranker for job match candidates (P3-06 / P6-03).

Uses a cross-encoder when available and ``rerank_enabled``; otherwise a
deterministic token-overlap scorer suitable for stub/offline mode.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r'[a-z0-9+#]+', re.I)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or '') if len(t) > 1}


def _overlap_score(query: str, document: str) -> float:
    q = _tokens(query)
    d = _tokens(document)
    if not q or not d:
        return 0.0
    return len(q & d) / float(len(q))


def _doc_text(job: dict[str, Any]) -> str:
    parts = [
        str(job.get('title') or ''),
        str(job.get('company') or ''),
        str(job.get('description') or ''),
    ]
    return ' '.join(parts)


def rerank_jobs(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    enabled: bool | None = None,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Re-score/reorder job candidates. Returns a new list (may be truncated)."""
    if not candidates:
        return []

    use_rerank = settings.rerank_enabled if enabled is None else enabled
    if not use_rerank:
        return list(candidates)

    limit = top_n if top_n is not None else settings.rerank_top_n
    pool = candidates[: max(1, min(int(limit), len(candidates)))]

    scores: list[float] | None = None
    try:
        from sentence_transformers import CrossEncoder

        model = CrossEncoder(settings.rerank_model)
        pairs = [[query, _doc_text(job)] for job in pool]
        raw = model.predict(pairs)
        scores = [float(s) for s in raw]
        logger.info('rerank used CrossEncoder %s on %s candidates', settings.rerank_model, len(pool))
    except Exception:
        logger.info('rerank falling back to token-overlap scorer')
        scores = [_overlap_score(query, _doc_text(job)) for job in pool]

    rescored: list[dict[str, Any]] = []
    for job, score in zip(pool, scores):
        item = dict(job)
        item['score'] = float(score)
        item['reranked'] = True
        rescored.append(item)
    rescored.sort(key=lambda j: j.get('score', 0.0), reverse=True)

    # Keep any candidates beyond top_n in original order after the reranked head
    if len(candidates) > len(pool):
        tail = [dict(j) for j in candidates[len(pool) :]]
        for item in tail:
            item.setdefault('reranked', False)
        rescored.extend(tail)
    return rescored
