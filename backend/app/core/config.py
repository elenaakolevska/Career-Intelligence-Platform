from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError
from pydantic import field_validator
from typing import Any


def _parse_list_value(value: Any) -> list[str]:
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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    database_url: str = 'postgresql+psycopg://postgres:postgres@db:5432/career_platform'
    test_database_url: str | None = None
    redis_url: str = 'redis://redis:6379/0'
    backend_cors_origins: list[str] = ['http://localhost:3000', 'http://localhost:5173']
    # LLM
    llm_provider: str = 'stub'
    llm_fallback_enabled: bool = True
    llm_fallback_order: list[str] = ['gemini', 'groq', 'ollama']

    # Gemini (primary)
    gemini_api_key: str | None = None
    gemini_model: str = 'gemini-3.6-flash'
    gemini_api_url: str = 'https://generativelanguage.googleapis.com/v1'

    # Groq (optional)
    groq_api_key: str | None = None
    groq_model: str | None = 'llama-3.1-70b-versatile'
    groq_api_url: str = 'https://api.groq.com/openai/v1'

    # Ollama (local fallback)
    ollama_url: str | None = None
    ollama_model: str | None = None

    # Client tuning
    llm_timeout: int = 60
    llm_retries: int = 3

    # CV upload
    cv_upload_dir: str = './uploads/cv'
    cv_max_upload_size_bytes: int = 5 * 1024 * 1024  # 5 MB

    @field_validator('backend_cors_origins', 'llm_fallback_order', mode='before')
    def _parse_string_lists(cls, value: Any) -> list[str]:
        """Allow configured list fields to be provided as JSON arrays or comma-separated strings."""
        return _parse_list_value(value)


try:
    settings = Settings()
except Exception as exc:  # fallback if .env parsing fails (malformed env value)
    class _SettingsNoEnv(Settings):
        model_config = SettingsConfigDict(env_file=None, extra='ignore')

    settings = _SettingsNoEnv()
