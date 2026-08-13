from __future__ import annotations

from typing import Any
import time

import httpx

try:
    from app.core.config import settings
except Exception:
    settings = None
from app.core.exceptions import ExternalServiceError


TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _current_settings():
    if settings is not None:
        return settings
    try:
        from app.core.config import settings as _settings
    except Exception:
        return None
    return _settings


def _normalize_provider_name(provider: str | None) -> str:
    return (provider or 'stub').strip().lower()


def _parse_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            import json

            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        except Exception:
            pass
        return [item.strip() for item in stripped.split(',') if item.strip()]
    return [str(value)]


def _response_text(response: httpx.Response | None) -> str | None:
    if response is None:
        return None
    try:
        return response.text
    except Exception:
        return None


def _is_transient_http_error(exc: BaseException | None) -> bool:
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, httpx.HTTPStatusError):
            status_code = getattr(getattr(current, 'response', None), 'status_code', None)
            return status_code in TRANSIENT_STATUS_CODES
        if isinstance(current, httpx.RequestError):
            return True
        current = current.__cause__ or current.__context__
    return False


def _request_with_retries(
    client: httpx.Client,
    url: str,
    *,
    payload: dict[str, Any],
    headers: dict[str, str] | None,
    retries: int,
    error_prefix: str,
) -> httpx.Response:
    max_attempts = max(1, retries)
    last_exc: Exception | None = None

    for attempt in range(max_attempts):
        try:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if _is_transient_http_error(exc) and attempt < max_attempts - 1:
                time.sleep(0.2 * (attempt + 1))
                continue
            body = _response_text(getattr(exc, 'response', None))
            raise ExternalServiceError(f'{error_prefix}: {exc} - body={body}') from exc
        except httpx.RequestError as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                time.sleep(0.2 * (attempt + 1))
                continue
            raise ExternalServiceError(f'{error_prefix}: {exc}') from exc

    raise ExternalServiceError(f'{error_prefix}: {last_exc}') from last_exc


class LLMClient:
    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise NotImplementedError()


class StubClient(LLMClient):
    def generate(self, prompt: str, **kwargs: Any) -> str:
        return f"[stub] {prompt}"


class GeminiClient(LLMClient):
    def __init__(
        self,
        api_key: str | None,
        model: str | None = None,
        api_url: str | None = None,
        timeout: int | None = None,
        retries: int | None = None,
    ):
        self.api_key = api_key
        current_settings = _current_settings()
        self.model = model or (current_settings.gemini_model if current_settings is not None else None)
        self.api_url = api_url or (current_settings.gemini_api_url if current_settings is not None else 'https://generativelanguage.googleapis.com/v1')
        self.timeout = timeout if timeout is not None else (current_settings.llm_timeout if current_settings is not None else 10)
        self.retries = retries if retries is not None else (current_settings.llm_retries if current_settings is not None else 3)
        self._client = httpx.Client(timeout=self.timeout)

    def generate(self, prompt: str, max_tokens: int = 512, **kwargs: Any) -> str:
        if not self.api_key:
            raise ExternalServiceError('Gemini API key not configured')
        if not self.model:
            raise ExternalServiceError('Gemini model not configured')
        if not self.api_url:
            raise ExternalServiceError('Gemini API URL not configured')

        # Normalize model name (allow 'models/...' or plain id)
        model_name = self.model
        if model_name.startswith('models/'):
            model_name = model_name.split('/', 1)[1]

        url = f"{self.api_url.rstrip('/')}/models/{model_name}:generateContent"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }

        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        response = _request_with_retries(
            self._client,
            url,
            payload=payload,
            headers=headers,
            retries=self.retries,
            error_prefix='Gemini request failed',
        )

        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError(f'Gemini response parsing failed: {exc}') from exc

        if isinstance(data, dict):
            candidates = data.get('candidates')
            if isinstance(candidates, list) and candidates:
                first = candidates[0]
                if isinstance(first, dict):
                    content = first.get('content') or {}
                    parts = content.get('parts') if isinstance(content, dict) else None
                    if isinstance(parts, list) and parts:
                        first_part = parts[0]
                        if isinstance(first_part, dict):
                            text = first_part.get('text')
                            if text:
                                return str(text)
            return str(data)
        return str(data)


class GroqClient(LLMClient):
    def __init__(
        self,
        api_key: str | None,
        model: str | None = None,
        api_url: str | None = None,
        timeout: int | None = None,
        retries: int | None = None,
    ):
        self.api_key = api_key
        current_settings = _current_settings()
        self.model = model or (current_settings.groq_model if current_settings is not None else None)
        self.api_url = api_url or (current_settings.groq_api_url if current_settings is not None else 'https://api.groq.com/openai/v1')
        self.timeout = timeout if timeout is not None else (current_settings.llm_timeout if current_settings is not None else 10)
        self.retries = retries if retries is not None else (current_settings.llm_retries if current_settings is not None else 3)
        self._client = httpx.Client(timeout=self.timeout)

    def generate(self, prompt: str, max_tokens: int = 512, **kwargs: Any) -> str:
        if not self.api_key:
            raise ExternalServiceError('Groq API key not configured')
        if not self.model:
            raise ExternalServiceError('Groq model not configured')
        if not self.api_url:
            raise ExternalServiceError('Groq API URL not configured')

        endpoint = f"{self.api_url.rstrip('/')}/chat/completions"
        payload = {
            'model': self.model,
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': max_tokens,
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
        }

        response = _request_with_retries(
            self._client,
            endpoint,
            payload=payload,
            headers=headers,
            retries=self.retries,
            error_prefix='Groq request failed',
        )

        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError(f'Groq response parsing failed: {exc}') from exc

        if isinstance(data, dict):
            choices = data.get('choices')
            if isinstance(choices, list) and choices:
                first_choice = choices[0]
                if isinstance(first_choice, dict):
                    message = first_choice.get('message') or {}
                    if isinstance(message, dict):
                        content = message.get('content')
                        if isinstance(content, list):
                            pieces: list[str] = []
                            for piece in content:
                                if isinstance(piece, dict):
                                    pieces.append(str(piece.get('text', '')))
                                else:
                                    pieces.append(str(piece))
                            text = ''.join(pieces).strip()
                            if text:
                                return text
                        if content:
                            return str(content)
                    text = first_choice.get('text')
                    if text:
                        return str(text)
            return str(data)
        return str(data)


class OllamaClient(LLMClient):
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        retries: int | None = None,
    ):
        self.url = url
        self.model = model
        current_settings = _current_settings()
        self.url = url or (current_settings.ollama_url if current_settings is not None else None)
        self.model = model or (current_settings.ollama_model if current_settings is not None else None)
        self.timeout = timeout if timeout is not None else (current_settings.llm_timeout if current_settings is not None else 10)
        self.retries = retries if retries is not None else (current_settings.llm_retries if current_settings is not None else 3)
        self._client = httpx.Client(timeout=self.timeout)

    def generate(self, prompt: str, max_tokens: int = 512, **kwargs: Any) -> str:
        if not self.url:
            raise ExternalServiceError('Ollama URL not configured')
        if not self.model:
            raise ExternalServiceError('Ollama model not configured')
        # Expecting full base URL in settings, construct endpoint
        endpoint = f"{self.url.rstrip('/')}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}

        response = _request_with_retries(
            self._client,
            endpoint,
            payload=payload,
            headers=None,
            retries=self.retries,
            error_prefix='Ollama request failed',
        )

        try:
            data = response.json()
        except ValueError as exc:
            raise ExternalServiceError(f'Ollama response parsing failed: {exc}') from exc

        if isinstance(data, dict):
            return data.get('response') or data.get('result') or data.get('output') or str(data)
        return str(data)


class FallbackLLMClient(LLMClient):
    def __init__(self, providers: list[tuple[str, LLMClient]]):
        self.providers = providers

    def generate(self, prompt: str, **kwargs: Any) -> str:
        last_error: ExternalServiceError | None = None
        for index, (provider_name, provider) in enumerate(self.providers):
            try:
                return provider.generate(prompt, **kwargs)
            except ExternalServiceError as exc:
                last_error = exc
                if not _is_transient_http_error(exc) or index >= len(self.providers) - 1:
                    raise
                continue
        if last_error is not None:
            raise last_error
        raise ExternalServiceError('No LLM provider available')


_singleton: LLMClient | None = None


def _build_provider_client(provider: str, current_settings: Any | None) -> LLMClient:
    timeout = current_settings.llm_timeout if current_settings is not None else None
    retries = current_settings.llm_retries if current_settings is not None else None

    if provider == 'gemini':
        return GeminiClient(
            api_key=current_settings.gemini_api_key if current_settings is not None else None,
            model=current_settings.gemini_model if current_settings is not None else None,
            api_url=current_settings.gemini_api_url if current_settings is not None else None,
            timeout=timeout,
            retries=retries,
        )
    if provider == 'groq':
        return GroqClient(
            api_key=current_settings.groq_api_key if current_settings is not None else None,
            model=current_settings.groq_model if current_settings is not None else None,
            api_url=current_settings.groq_api_url if current_settings is not None else None,
            timeout=timeout,
            retries=retries,
        )
    if provider == 'ollama':
        return OllamaClient(
            url=current_settings.ollama_url if current_settings is not None else None,
            model=current_settings.ollama_model if current_settings is not None else None,
            timeout=timeout,
            retries=retries,
        )
    return StubClient()


def _build_provider_sequence(provider: str, fallback_enabled: bool, fallback_order: list[str]) -> list[str]:
    normalized_order = [name for name in (_normalize_provider_name(item) for item in fallback_order) if name in {'gemini', 'groq', 'ollama'}]
    if provider == 'stub':
        return ['stub']
    if provider not in normalized_order:
        normalized_order = [provider] + [name for name in normalized_order if name != provider]
    else:
        normalized_order = normalized_order[normalized_order.index(provider):]
    if not fallback_enabled:
        return [provider]
    return normalized_order


def get_llm_client() -> LLMClient:
    global _singleton
    if _singleton is not None:
        return _singleton

    current_settings = _current_settings()
    provider = _normalize_provider_name(current_settings.llm_provider if current_settings is not None else 'stub')
    if provider not in {'gemini', 'groq', 'ollama', 'stub'}:
        provider = 'stub'

    if provider == 'stub':
        _singleton = StubClient()
        return _singleton

    fallback_enabled = current_settings.llm_fallback_enabled if current_settings is not None else False
    fallback_order = current_settings.llm_fallback_order if current_settings is not None else [provider]
    provider_sequence = _build_provider_sequence(provider, fallback_enabled, fallback_order)
    provider_clients = [(name, _build_provider_client(name, current_settings)) for name in provider_sequence]

    if len(provider_clients) == 1:
        _singleton = provider_clients[0][1]
    else:
        _singleton = FallbackLLMClient(provider_clients)
    return _singleton


__all__ = ['LLMClient', 'get_llm_client']
