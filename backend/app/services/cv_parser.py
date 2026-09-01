"""LLM-backed CV parsing with JSON repair and Pydantic validation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.clients.llm_client import LLMClient, get_llm_client
from app.core.config import settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.schemas.cv import StructuredCV
from app.services.heuristic_cv_parser import heuristic_parse_cv
from app.services.prompt_loader import render_cv_extraction_prompt

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r'```(?:json)?\s*(.*?)\s*```', re.DOTALL | re.IGNORECASE)


def extract_json_payload(text: str) -> str:
    """Pull the most likely JSON object out of an LLM response.

    Accepts truncated objects (no closing ``}``) so repair_json can finish them —
    Gemini often cuts mid-string when maxOutputTokens is tight.
    """
    stripped = (text or '').strip()
    if not stripped:
        raise ValidationError('LLM returned empty response')

    fence = _JSON_FENCE_RE.search(stripped)
    if fence:
        stripped = fence.group(1).strip()

    start = stripped.find('{')
    if start == -1:
        raise ValidationError('LLM response did not contain a JSON object')
    end = stripped.rfind('}')
    if end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped[start:]


def _close_truncated_json(raw: str) -> str:
    """Best-effort close for truncated JSON objects/arrays/strings."""
    s = (raw or '').rstrip()
    if not s:
        return s

    in_string = False
    escape = False
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        s += '"'

    # Drop a trailing comma before we close
    s = re.sub(r',\s*$', '', s)

    opens_obj = s.count('{') - s.count('}')
    opens_arr = s.count('[') - s.count(']')
    s += ']' * max(0, opens_arr)
    s += '}' * max(0, opens_obj)
    return s


def repair_json(raw: str) -> Any:
    """Parse JSON, attempting light repairs for common LLM mistakes."""
    candidates = [raw]
    # Trailing commas
    candidates.append(re.sub(r',\s*([}\]])', r'\1', raw))
    # Smart quotes
    candidates.append(raw.replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'"))
    # Truncated payloads (missing closing quotes/braces)
    candidates.append(_close_truncated_json(raw))
    candidates.append(_close_truncated_json(re.sub(r',\s*([}\]])', r'\1', raw)))

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
    raise ValidationError(f'Malformed JSON from LLM: {last_error}') from last_error


def validate_structured_cv(data: Any) -> StructuredCV:
    try:
        structured = StructuredCV.model_validate(data)
    except PydanticValidationError as exc:
        raise ValidationError(f'CV structured data failed schema validation: {exc}') from exc

    if not structured.skills:
        logger.warning('CV validation: zero skills extracted')
    if not structured.name and not structured.email and not structured.experience:
        raise ValidationError(
            'CV extraction too sparse: missing name/email/experience — refusing to accept empty profile'
        )
    return structured


class CVParserService:
    def __init__(self, llm: LLMClient | None = None, max_attempts: int = 2) -> None:
        self.llm = llm or get_llm_client()
        self.max_attempts = max_attempts

    def parse(self, raw_text: str) -> StructuredCV:
        if not raw_text or not raw_text.strip():
            raise ValidationError('Cannot parse empty CV text')

        # Offline/dev stub path: deterministic heuristic extraction (no live LLM)
        if (settings.llm_provider or 'stub').strip().lower() == 'stub':
            return validate_structured_cv(heuristic_parse_cv(raw_text).model_dump())

        prompt = render_cv_extraction_prompt(raw_text)
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                repair_hint = ''
                if attempt > 1:
                    repair_hint = (
                        '\n\nPrevious output was invalid JSON. '
                        'Respond with ONLY a valid JSON object matching the schema.'
                    )
                response = self.llm.generate(prompt + repair_hint, max_tokens=4096, json_mode=True)
                payload = extract_json_payload(response)
                data = repair_json(payload)
                return validate_structured_cv(data)
            except (ValidationError, ExternalServiceError) as exc:
                last_error = exc
                logger.warning(
                    'CV parse attempt %s failed: %s | response_preview=%r',
                    attempt,
                    exc,
                    (response[:240] if 'response' in locals() and response else None),
                )
                continue

        logger.warning(
            'CV LLM parse failed after %s attempts (%s); falling back to heuristic parser',
            self.max_attempts,
            last_error,
        )
        try:
            return validate_structured_cv(heuristic_parse_cv(raw_text).model_dump())
        except ValidationError:
            raise ValidationError(
                f'CV parsing failed after {self.max_attempts} attempts: {last_error}'
            ) from last_error
