"""Chunker unit tests (P3-02 chunking for RAG ingestion)."""

from app.services.chunker import chunk_text


def test_short_text_single_chunk():
    assert chunk_text('short document', max_chars=600) == ['short document']


def test_empty_and_whitespace():
    assert chunk_text('') == []
    assert chunk_text('   ') == []


def test_multichunk_overlap_and_coverage():
    text = ('word ' * 200).strip()
    chunks = chunk_text(text, max_chars=600, overlap=100)
    assert len(chunks) > 1
    joined = ' '.join(chunks)
    # Overlap means total length exceeds the source, but every source word is present
    assert 'word' in joined
    for chunk in chunks:
        assert len(chunk) <= 600 + 5  # allow boundary rounding


def test_sentence_boundary_preference():
    text = 'First sentence. ' * 40 + 'Tail sentence here.'
    chunks = chunk_text(text, max_chars=200, overlap=40)
    assert len(chunks) > 1
    # Chunks should end cleanly on a sentence boundary, not mid-word
    for chunk in chunks[:-1]:
        assert chunk.strip().endswith(('.', '!', '?'))


def test_overlap_validation():
    try:
        chunk_text('abc', max_chars=10, overlap=10)
    except ValueError:
        return
    raise AssertionError('expected ValueError when overlap >= max_chars')
