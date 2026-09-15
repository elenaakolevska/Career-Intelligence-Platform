"""Deterministic groundedness check (no LLM required).

Reuses the production grounding guardrails: the exact empty-context hedge
markers and the shared citation validator.
"""

from __future__ import annotations

from typing import Any, Sequence

from app.services.citations import validate_citations
from app.services.prompt_loader import NO_CONTEXT_MARKERS
from app.services.rag_pipeline import extract_citations


def is_hedge(answer: str) -> bool:
    """True when the answer is one of the explicit empty-context hedges."""
    text = (answer or '').strip()
    return any(marker in text for marker in NO_CONTEXT_MARKERS)


def deterministic_groundedness(
    answer: str,
    context_items: Sequence[Any],
    *,
    empty_context: bool,
) -> dict[str, Any]:
    """Return a groundedness verdict using only deterministic signals.

    - Empty context: grounded iff the answer is the explicit hedge (never a
      confident fabrication).
    - Non-empty context: grounded iff the answer cites at least one actually
      retrieved item (and cites nothing that was not retrieved).
    """
    if empty_context:
        return {
            'grounded': is_hedge(answer),
            'empty_context': True,
            'reason': 'empty-context hedge expected',
        }

    text = (answer or '').strip()
    if not text:
        return {'grounded': False, 'empty_context': False, 'reason': 'empty answer'}

    valid, invalid = validate_citations(extract_citations(answer), context_items)
    return {
        'grounded': len(valid) > 0 and len(invalid) == 0,
        'empty_context': False,
        'reason': 'cites retrieved context' if valid else 'no verifiable citation',
        'valid_citations': len(valid),
        'invalid_citations': len(invalid),
    }
