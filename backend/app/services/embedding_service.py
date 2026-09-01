"""Embedding service wrapping sentence-transformers (or a deterministic stub).

Decision (P3-02): embed a single whole-profile document built from structured
fields + raw summary. Tradeoff: simpler FAISS mapping and search vs. finer
per-section retrieval. Whole-CV is enough for MVP job matching; per-entry
can be added later without changing the public embed() API.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from typing import Sequence

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def _stub_embed(texts: Sequence[str]) -> np.ndarray:
    """Deterministic bag-of-tokens embedding for tests / offline CI."""
    dim = settings.embedding_dim
    vectors = []
    for text in texts:
        vec = np.zeros(dim, dtype='float32')
        tokens = [t for t in ''.join(ch.lower() if ch.isalnum() else ' ' for ch in (text or '')).split() if t]
        if not tokens:
            tokens = ['empty']
        for token in tokens:
            digest = hashlib.md5(token.encode('utf-8')).digest()
            idx = int.from_bytes(digest[:4], 'little') % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vec[idx] += sign
            # Spread a few more dimensions per token for stability
            idx2 = int.from_bytes(digest[5:9], 'little') % dim
            vec[idx2] += 0.5 * sign
        norm = float(np.linalg.norm(vec)) or 1.0
        vectors.append(vec / norm)
    return np.vstack(vectors).astype('float32')


def _load_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from sentence_transformers import SentenceTransformer

        logger.info('Loading embedding model %s once', settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        return _model


def embed(texts: str | Sequence[str]) -> np.ndarray:
    """Embed one string or a batch. Returns shape (n, dim) float32 L2-normalized."""
    if isinstance(texts, str):
        batch = [texts]
    else:
        batch = list(texts)
    if not batch:
        return np.zeros((0, settings.embedding_dim), dtype='float32')

    if settings.embedding_use_stub or settings.llm_provider == 'stub':
        return _stub_embed(batch)

    try:
        model = _load_model()
        vectors = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
        arr = np.asarray(vectors, dtype='float32')
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        return arr
    except Exception:
        logger.exception('sentence-transformers failed; falling back to stub embeddings')
        return _stub_embed(batch)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.reshape(-1)
    b = b.reshape(-1)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(np.dot(a, b) / denom)


def build_cv_embedding_text(structured: dict | None, raw_text: str | None, summary: str | None) -> str:
    parts: list[str] = []
    if summary:
        parts.append(summary)
    if structured:
        if structured.get('name'):
            parts.append(str(structured['name']))
        skills = structured.get('skills') or []
        if skills:
            parts.append('Skills: ' + ', '.join(skills))
        for exp in structured.get('experience') or []:
            bits = [exp.get('title'), exp.get('company'), exp.get('description')]
            parts.append(' | '.join(str(b) for b in bits if b))
        for edu in structured.get('education') or []:
            bits = [edu.get('degree'), edu.get('institution')]
            parts.append(' | '.join(str(b) for b in bits if b))
    if not parts and raw_text:
        parts.append(raw_text[:4000])
    return '\n'.join(parts)


def build_job_embedding_text(job) -> str:
    parts = [job.title or '']
    if job.company:
        parts.append(job.company)
    if job.location:
        parts.append(job.location)
    if job.description:
        parts.append(job.description[:3000])
    return '\n'.join(parts)
