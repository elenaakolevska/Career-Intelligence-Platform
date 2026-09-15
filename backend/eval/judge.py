"""Optional LLM-as-judge answer-quality evaluation (never required for CI)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.clients.llm_client import StubClient, get_llm_client
from app.core.config import settings

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """You are evaluating an AI career-analysis explanation for correctness and usefulness.

Score each dimension from 1 (poor) to 5 (excellent). Return ONLY a JSON object
with keys "relevance", "specificity", "groundedness", "usefulness".

- relevance: how well the answer addresses the question
- specificity: how concrete and non-generic the answer is
- groundedness: whether the answer stays within the provided context
- usefulness: how actionable the explanation is for the user

QUESTION:
{{QUESTION}}

CONTEXT:
{{CONTEXT}}

ANSWER:
{{ANSWER}}
"""

_DIMENSIONS = ('relevance', 'specificity', 'groundedness', 'usefulness')


def _parse_scores(raw: str) -> dict[str, int] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find('{')
        end = raw.rfind('}')
        if start == -1 or end == -1:
            return None
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    scores: dict[str, int] = {}
    for dim in _DIMENSIONS:
        value = data.get(dim)
        if isinstance(value, (int, float)):
            scores[dim] = max(1, min(5, int(round(value))))
    return scores if scores else None


def judge_answer(
    question: str,
    answer: str,
    context: str,
    *,
    llm: Any = None,
) -> dict[str, Any] | None:
    """Score an answer with the configured LLM. Returns None in stub mode or on failure."""
    client = llm or get_llm_client()
    if isinstance(client, StubClient) or (settings.llm_provider or '').lower() == 'stub':
        return None

    prompt = (
        _JUDGE_PROMPT.replace('{{QUESTION}}', question)
        .replace('{{CONTEXT}}', (context or '')[:6000])
        .replace('{{ANSWER}}', answer)
    )
    try:
        raw = client.generate(prompt, max_tokens=256)
    except Exception as exc:  # noqa: BLE001 — judge is best-effort
        logger.warning('LLM judge failed: %s', exc)
        return None
    return {'scores': _parse_scores(raw)}
