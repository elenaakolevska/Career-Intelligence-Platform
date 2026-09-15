"""Simple, dependency-free sliding-window text chunker for RAG ingestion.

Splits a document into overlapping windows so retrieval can address finer
granularity than whole-document embeddings and carry chunk-level provenance.
"""

from __future__ import annotations


def _boundary_cut(window: str, max_chars: int) -> int | None:
    """Return an index to cut ``window`` at a sentence/word boundary.

    Prefers a sentence boundary in the second half of the window, then the
    last word boundary. Returns ``None`` when no clean boundary exists.
    """
    lower = max_chars // 2
    for sep in ('. ', '! ', '? ', '\n'):
        idx = window.rfind(sep, lower, max_chars)
        if idx != -1:
            return idx + len(sep)
    idx = window.rfind(' ', lower, max_chars)
    if idx != -1:
        return idx + 1
    return None


def chunk_text(text: str, *, max_chars: int = 600, overlap: int = 100) -> list[str]:
    """Split ``text`` into overlapping chunks of roughly ``max_chars``.

    - Normalizes whitespace.
    - Short documents (<= max_chars) return a single chunk.
    - Longer documents break at sentence/word boundaries with ``overlap``
      characters of context shared between consecutive chunks.
    """
    normalized = ' '.join((text or '').split())
    if not normalized:
        return []
    if overlap >= max_chars:
        raise ValueError('overlap must be smaller than max_chars')
    if len(normalized) <= max_chars:
        return [normalized]

    chunks: list[str] = []
    start = 0
    n = len(normalized)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            cut = _boundary_cut(normalized[start:end], max_chars)
            if cut is not None:
                end = start + cut
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks
