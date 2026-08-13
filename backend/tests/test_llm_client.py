from types import SimpleNamespace

import httpx
import pytest

from app.clients import llm_client
from app.clients.llm_client import (
    FallbackLLMClient,
    GeminiClient,
    GroqClient,
    OllamaClient,
    StubClient,
    get_llm_client,
)
from app.core.exceptions import ExternalServiceError


GEMINI_URL = 'https://generativelanguage.googleapis.com/v1'
GROQ_URL = 'https://api.groq.com/openai/v1'
OLLAMA_URL = 'http://localhost:11434'


def _fake_settings(**overrides):
    defaults = {
        'llm_provider': 'gemini',
        'llm_fallback_enabled': True,
        'llm_fallback_order': ['gemini', 'groq', 'ollama'],
        'gemini_api_key': 'gemini-key',
        'gemini_model': 'gemini-model',
        'gemini_api_url': GEMINI_URL,
        'groq_api_key': 'groq-key',
        'groq_model': 'groq-model',
        'groq_api_url': GROQ_URL,
        'ollama_url': OLLAMA_URL,
        'ollama_model': 'ollama-model',
        'llm_timeout': 10,
        'llm_retries': 3,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _http_status_error(method: str, url: str, status_code: int, body: str) -> httpx.HTTPStatusError:
    request = httpx.Request(method, url)
    response = httpx.Response(status_code, request=request, content=body.encode('utf-8'))
    return httpx.HTTPStatusError('boom', request=request, response=response)


def _http_timeout_error(method: str, url: str) -> httpx.ReadTimeout:
    request = httpx.Request(method, url)
    return httpx.ReadTimeout('timeout', request=request)


def test_llm_client_stub_behaviour() -> None:
    llm_client._singleton = None
    llm_client.settings = _fake_settings(llm_provider='stub')

    client = get_llm_client()
    assert isinstance(client, StubClient)
    assert 'hello world' in client.generate('hello world')


def test_get_llm_client_builds_fallback_chain(monkeypatch) -> None:
    llm_client._singleton = None
    monkeypatch.setattr(llm_client, 'settings', _fake_settings(llm_provider='gemini', llm_fallback_enabled=True), raising=False)

    client = get_llm_client()
    assert isinstance(client, FallbackLLMClient)


def test_gemini_client_success(monkeypatch) -> None:
    client = GeminiClient(api_key='fake', model='gemini-model', api_url=GEMINI_URL, retries=1)

    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {'candidates': [{'content': {'parts': [{'text': 'generated text'}]}}]}

    def fake_post(self, url, json=None, headers=None):
        return DummyResp()

    monkeypatch.setattr(httpx.Client, 'post', fake_post)
    assert client.generate('prompt') == 'generated text'


def test_gemini_client_error_does_not_hide_client_error(monkeypatch) -> None:
    client = GeminiClient(api_key='fake', model='gemini-model', api_url=GEMINI_URL, retries=2)
    calls: list[str] = []

    def fake_post(self, url, json=None, headers=None):
        calls.append(url)
        raise _http_status_error('POST', url, 400, 'bad request')

    monkeypatch.setattr(httpx.Client, 'post', fake_post)

    with pytest.raises(ExternalServiceError, match='Gemini request failed'):
        client.generate('prompt')
    assert len(calls) == 1


def test_gemini_client_missing_credentials() -> None:
    client = GeminiClient(api_key=None, model='gemini-model', api_url=GEMINI_URL)

    with pytest.raises(ExternalServiceError, match='Gemini API key not configured'):
        client.generate('prompt')


def test_gemini_client_retries_on_timeout(monkeypatch) -> None:
    client = GeminiClient(api_key='fake', model='gemini-model', api_url=GEMINI_URL, retries=3)
    calls: list[str] = []

    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {'candidates': [{'content': {'parts': [{'text': 'eventual success'}]}}]}

    def fake_post(self, url, json=None, headers=None):
        calls.append(url)
        if len(calls) < 3:
            raise _http_timeout_error('POST', url)
        return DummyResp()

    monkeypatch.setattr(httpx.Client, 'post', fake_post)

    assert client.generate('prompt') == 'eventual success'
    assert len(calls) == 3


def test_groq_client_success(monkeypatch) -> None:
    client = GroqClient(api_key='groq-key', model='groq-model', api_url=GROQ_URL, retries=1)

    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {'choices': [{'message': {'content': 'groq output'}}]}

    def fake_post(self, url, json=None, headers=None):
        assert url == f'{GROQ_URL}/chat/completions'
        assert headers['Authorization'] == 'Bearer groq-key'
        return DummyResp()

    monkeypatch.setattr(httpx.Client, 'post', fake_post)
    assert client.generate('prompt') == 'groq output'


def test_groq_client_missing_credentials() -> None:
    client = GroqClient(api_key=None, model='groq-model', api_url=GROQ_URL)

    with pytest.raises(ExternalServiceError, match='Groq API key not configured'):
        client.generate('prompt')


def test_groq_client_http_error(monkeypatch) -> None:
    client = GroqClient(api_key='groq-key', model='groq-model', api_url=GROQ_URL, retries=2)
    calls: list[str] = []

    def fake_post(self, url, json=None, headers=None):
        calls.append(url)
        raise _http_status_error('POST', url, 401, 'unauthorized')

    monkeypatch.setattr(httpx.Client, 'post', fake_post)

    with pytest.raises(ExternalServiceError, match='Groq request failed'):
        client.generate('prompt')
    assert len(calls) == 1


def test_ollama_client_success(monkeypatch) -> None:
    client = OllamaClient(url=OLLAMA_URL, model='ollama-model', retries=1)

    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {'response': 'ollama output'}

    def fake_post(self, url, json=None, headers=None):
        assert url == f'{OLLAMA_URL}/api/generate'
        assert json['stream'] is False
        return DummyResp()

    monkeypatch.setattr(httpx.Client, 'post', fake_post)
    assert client.generate('prompt') == 'ollama output'


def test_ollama_client_missing_url(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, 'settings', _fake_settings(ollama_url=None, ollama_model='ollama-model'), raising=False)
    client = OllamaClient(url=None, model=None)

    with pytest.raises(ExternalServiceError, match='Ollama URL not configured'):
        client.generate('prompt')


def test_ollama_client_retries_on_timeout(monkeypatch) -> None:
    client = OllamaClient(url=OLLAMA_URL, model='ollama-model', retries=3)
    calls: list[str] = []

    class DummyResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {'response': 'ollama recovered'}

    def fake_post(self, url, json=None, headers=None):
        calls.append(url)
        if len(calls) < 3:
            raise _http_timeout_error('POST', url)
        return DummyResp()

    monkeypatch.setattr(httpx.Client, 'post', fake_post)

    assert client.generate('prompt') == 'ollama recovered'
    assert len(calls) == 3


def test_fallback_chain_gemini_to_groq(monkeypatch) -> None:
    gemini_client = GeminiClient(api_key='gemini-key', model='gemini-model', api_url=GEMINI_URL, retries=1)
    groq_client = GroqClient(api_key='groq-key', model='groq-model', api_url=GROQ_URL, retries=1)
    fallback_client = FallbackLLMClient([
        ('gemini', gemini_client),
        ('groq', groq_client),
    ])

    class GroqResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {'choices': [{'message': {'content': 'fallback answer'}}]}

    def fake_post(self, url, json=None, headers=None):
        if url.startswith(GEMINI_URL):
            raise _http_status_error('POST', url, 503, 'gemini unavailable')
        return GroqResp()

    monkeypatch.setattr(httpx.Client, 'post', fake_post)

    assert fallback_client.generate('prompt') == 'fallback answer'


def test_fallback_chain_groq_to_ollama(monkeypatch) -> None:
    groq_client = GroqClient(api_key='groq-key', model='groq-model', api_url=GROQ_URL, retries=1)
    ollama_client = OllamaClient(url=OLLAMA_URL, model='ollama-model', retries=1)
    fallback_client = FallbackLLMClient([
        ('groq', groq_client),
        ('ollama', ollama_client),
    ])

    class OllamaResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {'response': 'ollama fallback answer'}

    def fake_post(self, url, json=None, headers=None):
        if url.startswith(GROQ_URL):
            raise _http_status_error('POST', url, 503, 'groq unavailable')
        return OllamaResp()

    monkeypatch.setattr(httpx.Client, 'post', fake_post)

    assert fallback_client.generate('prompt') == 'ollama fallback answer'


def test_auth_failure_does_not_fallback(monkeypatch) -> None:
    gemini_client = GeminiClient(api_key='gemini-key', model='gemini-model', api_url=GEMINI_URL, retries=1)
    groq_client = GroqClient(api_key='groq-key', model='groq-model', api_url=GROQ_URL, retries=1)
    fallback_client = FallbackLLMClient([
        ('gemini', gemini_client),
        ('groq', groq_client),
    ])

    def fake_post(self, url, json=None, headers=None):
        raise _http_status_error('POST', url, 401, 'invalid api key')

    monkeypatch.setattr(httpx.Client, 'post', fake_post)

    with pytest.raises(ExternalServiceError, match='Gemini request failed'):
        fallback_client.generate('prompt')