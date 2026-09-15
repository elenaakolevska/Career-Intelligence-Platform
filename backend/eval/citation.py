"""Citation correctness evaluation.

Reuses the production validation system (``app.services.citations``) so the
eval measures the same thing the report flow enforces.
"""

from __future__ import annotations

from typing import Any, Sequence

from app.services.citations import validate_citations
from app.services.rag_pipeline import extract_citations


def evaluate_citations(answer: str, context_items: Sequence[Any]) -> dict[str, Any]:
    """Evaluate citation correctness of a generated answer.

    Returns ``valid`` (canonical refs), ``invalid`` (hallucinated refs), and
    ``accuracy`` (fraction of citations that are valid; None when no citations).
    """
    refs = extract_citations(answer)
    valid, invalid = validate_citations(refs, context_items)
    total = len(valid) + len(invalid)
    return {
        'valid': [c['ref'] for c in valid],
        'invalid': invalid,
        'total': total,
        'accuracy': (len(valid) / total) if total else None,
    }
