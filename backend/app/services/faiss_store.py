"""Persistent vector store with FAISS when available, NumPy cosine fallback otherwise."""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()

try:
    import faiss  # type: ignore

    _HAS_FAISS = True
except Exception:
    faiss = None  # type: ignore
    _HAS_FAISS = False
    logger.warning('faiss not installed; using NumPy cosine store')


class FaissStore:
    """IndexFlatIP on L2-normalized vectors (cosine). Falls back to NumPy if FAISS missing."""

    def __init__(self, name: str, dim: int | None = None, index_dir: str | None = None) -> None:
        self.name = name
        self.dim = dim or settings.embedding_dim
        self.root = Path(index_dir or settings.faiss_index_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / f'{name}.faiss'
        self.map_path = self.root / f'{name}_ids.json'
        self.vectors_path = self.root / f'{name}_vectors.npy'
        self._index = None
        self._ids: list[str] = []
        self._vectors: np.ndarray = np.zeros((0, self.dim), dtype='float32')
        self._load()

    def _new_index(self):
        if _HAS_FAISS:
            return faiss.IndexFlatIP(self.dim)
        return None

    def _load(self) -> None:
        if self.map_path.exists() and self.vectors_path.exists():
            self._ids = json.loads(self.map_path.read_text(encoding='utf-8'))
            self._vectors = np.load(self.vectors_path)
            if _HAS_FAISS and self.index_path.exists():
                self._index = faiss.read_index(str(self.index_path))
            elif _HAS_FAISS and len(self._vectors):
                self._index = self._new_index()
                self._index.add(self._vectors.astype('float32'))
            logger.info('Loaded vector index %s with %s vectors', self.name, len(self._ids))
        else:
            self._index = self._new_index()
            self._ids = []
            self._vectors = np.zeros((0, self.dim), dtype='float32')

    def save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.map_path.write_text(json.dumps(self._ids), encoding='utf-8')
        np.save(self.vectors_path, self._vectors)
        if _HAS_FAISS and self._index is not None:
            faiss.write_index(self._index, str(self.index_path))

    def add(self, entity_id: str, vector: np.ndarray) -> None:
        with _lock:
            vec = np.asarray(vector, dtype='float32').reshape(1, -1)
            if entity_id in self._ids:
                self._remove_unlocked(entity_id)
            self._ids.append(str(entity_id))
            self._vectors = vec if len(self._vectors) == 0 else np.vstack([self._vectors, vec])
            if _HAS_FAISS:
                if self._index is None:
                    self._index = self._new_index()
                self._index.add(vec)
            self.save()

    def _remove_unlocked(self, entity_id: str) -> None:
        if entity_id not in self._ids:
            return
        keep = [i for i, eid in enumerate(self._ids) if eid != entity_id]
        self._ids = [self._ids[i] for i in keep]
        self._vectors = self._vectors[keep] if keep else np.zeros((0, self.dim), dtype='float32')
        if _HAS_FAISS:
            self._index = self._new_index()
            if len(self._vectors):
                self._index.add(self._vectors.astype('float32'))

    def search(self, vector: np.ndarray, top_k: int = 10) -> list[tuple[str, float]]:
        if len(self._ids) == 0:
            return []
        k = min(max(1, top_k), len(self._ids))
        vec = np.asarray(vector, dtype='float32').reshape(1, -1)
        if _HAS_FAISS and self._index is not None and self._index.ntotal > 0:
            scores, indices = self._index.search(vec, k)
            results: list[tuple[str, float]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self._ids):
                    continue
                results.append((self._ids[idx], float(score)))
            return results

        # NumPy cosine (vectors assumed normalized)
        sims = (self._vectors @ vec.reshape(-1)).astype('float32')
        top_idx = np.argsort(-sims)[:k]
        return [(self._ids[int(i)], float(sims[int(i)])) for i in top_idx]

    @property
    def size(self) -> int:
        return len(self._ids)


_stores: dict[str, FaissStore] = {}


def get_store(name: str, index_dir: str | None = None) -> FaissStore:
    key = f'{name}:{index_dir or settings.faiss_index_dir}'
    if key not in _stores:
        _stores[key] = FaissStore(name, index_dir=index_dir)
    return _stores[key]


def reset_stores() -> None:
    _stores.clear()
