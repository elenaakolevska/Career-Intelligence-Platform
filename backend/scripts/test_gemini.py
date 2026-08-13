import sys
from pathlib import Path

# Ensure local `app` package in backend/ is imported instead of any installed 'app' package
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from app.core.config import settings
from app.clients.llm_client import GeminiClient, StubClient


def main() -> None:
    provider = settings.llm_provider
    print('LLM provider:', provider)
    if provider == 'gemini':
        client = GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            api_url=settings.gemini_api_url,
        )
    else:
        client = StubClient()

    prompt = 'Summarize the following in one sentence: The quick brown fox jumps over the lazy dog.'
    try:
        out = client.generate(prompt)
        print('\n== Response ==')
        print(out)
    except Exception as exc:
        print('\n== Error calling LLM ==')
        print(repr(exc))


if __name__ == '__main__':
    main()
