import argparse
import sys
from pathlib import Path


# Ensure local `app` package in backend/ is imported instead of any installed 'app' package
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from app.clients.llm_client import GeminiClient, GroqClient, OllamaClient, StubClient, get_llm_client
from app.core.config import settings


def _build_client(provider: str):
    if provider == 'auto':
        return get_llm_client()
    if provider == 'gemini':
        return GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            api_url=settings.gemini_api_url,
            timeout=settings.llm_timeout,
            retries=settings.llm_retries,
        )
    if provider == 'groq':
        return GroqClient(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            api_url=settings.groq_api_url,
            timeout=settings.llm_timeout,
            retries=settings.llm_retries,
        )
    if provider == 'ollama':
        return OllamaClient(
            url=settings.ollama_url,
            model=settings.ollama_model,
            timeout=settings.llm_timeout,
            retries=settings.llm_retries,
        )
    return StubClient()


def main() -> None:
    parser = argparse.ArgumentParser(description='Test the configured LLM provider')
    parser.add_argument('--provider', choices=['auto', 'gemini', 'groq', 'ollama', 'stub'], default='auto')
    parser.add_argument('--prompt', default='Summarize the following in one sentence: The quick brown fox jumps over the lazy dog.')
    args = parser.parse_args()

    client = _build_client(args.provider)
    print('Selected provider:', args.provider)
    print('LLM client:', client.__class__.__name__)

    try:
        out = client.generate(args.prompt)
        print('\n== Response ==')
        print(out)
    except Exception as exc:
        print('\n== Error calling LLM ==')
        print(repr(exc))


if __name__ == '__main__':
    main()