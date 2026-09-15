import logging
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Any
from functools import lru_cache

logger = logging.getLogger(__name__)

# Known-insecure values: if the secret is unset or one of these is used,
# an ephemeral random secret is generated instead so tokens are never
# signed with a publicly guessable key.
INSECURE_JWT_SECRETS = {
    'skillbridge-dev-secret-change-me',
    'changeme',
    'change-me',
    'secret',
    'dev-secret',
}


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

    # Paths
    prompts_dir: str = '../prompts'
    cv_upload_dir: str = './uploads/cv'
    cv_max_upload_size_bytes: int = 5 * 1024 * 1024  # 5 MB
    faiss_index_dir: str = './data/faiss'

    # LLM
    llm_provider: str = 'stub'
    llm_fallback_enabled: bool = True
    llm_fallback_order: list[str] = ['gemini', 'groq', 'ollama']
    gemini_api_key: str | None = None
    gemini_model: str = 'gemini-2.0-flash'
    gemini_api_url: str = 'https://generativelanguage.googleapis.com/v1'
    groq_api_key: str | None = None
    groq_model: str | None = 'llama-3.1-70b-versatile'
    groq_api_url: str = 'https://api.groq.com/openai/v1'
    ollama_url: str | None = None
    ollama_model: str | None = None
    llm_timeout: int = 60
    llm_retries: int = 3

    # PDF / OCR
    ocr_enabled: bool = True
    ocr_min_chars: int = 80
    ocr_timeout_seconds: int = 60
    ocr_languages: list[str] = ['en']

    # Embeddings / search
    embedding_model: str = 'BAAI/bge-small-en-v1.5'
    embedding_dim: int = 384
    embedding_use_stub: bool = False
    similarity_top_k: int = 10
    retrieval_top_k: int = 5
    rerank_enabled: bool = False
    rerank_model: str = 'BAAI/bge-reranker-base'
    rerank_top_n: int = 20

    # Adzuna
    adzuna_app_id: str | None = None
    adzuna_api_key: str | None = None
    adzuna_base_url: str = 'https://api.adzuna.com/v1/api/jobs'
    adzuna_country: str = 'gb'
    adzuna_use_mock: bool = True
    adzuna_cache_ttl_seconds: int = 3600
    adzuna_monthly_budget: int = 250

    # SerpAPI / Open Library
    serpapi_api_key: str | None = None
    serpapi_cache_ttl_seconds: int = 86400

    # Auth / JWT
    jwt_secret: str | None = None
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Feature flags
    enable_cv_llm_parse: bool = True
    enable_ats_scoring: bool = True
    enable_auto_embed: bool = True

    @field_validator('jwt_secret', mode='before')
    @classmethod
    def _ensure_jwt_secret(cls, value: Any) -> str:
        if not value or str(value).strip().lower() in INSECURE_JWT_SECRETS:
            logger.warning(
                'JWT_SECRET is not set or uses an insecure default; '
                'generated an ephemeral random secret. Set JWT_SECRET in the '
                'environment for persistent login sessions.'
            )
            return secrets.token_urlsafe(48)
        return str(value)

    @field_validator(
        'backend_cors_origins',
        'llm_fallback_order',
        'ocr_languages',
        mode='before',
    )
    @classmethod
    def _parse_string_lists(cls, value: Any) -> list[str]:
        return _parse_list_value(value)


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception:
        class _SettingsNoEnv(Settings):
            model_config = SettingsConfigDict(env_file=None, extra='ignore')

        return _SettingsNoEnv()


settings = get_settings()
