"""Adzuna Jobs API client with rate-limit awareness and ExternalServiceError wrapping."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)

# Process-local call counter for free-tier safeguard (250/month)
_call_count = 0
_call_month = time.strftime('%Y-%m')


def _budget_ok() -> bool:
    global _call_count, _call_month
    month = time.strftime('%Y-%m')
    if month != _call_month:
        _call_month = month
        _call_count = 0
    return _call_count < settings.adzuna_monthly_budget


def _increment_calls() -> None:
    global _call_count
    _call_count += 1


class AdzunaClient:
    def __init__(
        self,
        app_id: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        country: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.app_id = app_id if app_id is not None else settings.adzuna_app_id
        self.api_key = api_key if api_key is not None else settings.adzuna_api_key
        self.base_url = (base_url or settings.adzuna_base_url).rstrip('/')
        self.country = country or settings.adzuna_country
        self.timeout = timeout
        self._client = httpx.Client(timeout=self.timeout)

    def search(self, *, what: str, where: str | None = None, results_per_page: int = 20, page: int = 1) -> dict[str, Any]:
        if not self.app_id or not self.api_key:
            raise ExternalServiceError('Adzuna credentials not configured')
        if not _budget_ok():
            raise ExternalServiceError('Adzuna monthly request budget exhausted')

        url = f'{self.base_url}/{self.country}/search/{page}'
        params = {
            'app_id': self.app_id,
            'app_key': self.api_key,
            'results_per_page': results_per_page,
            'what': what,
        }
        if where:
            params['where'] = where

        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
            _increment_calls()
            return response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text if exc.response is not None else ''
            raise ExternalServiceError(f'Adzuna request failed: {exc} - body={body}') from exc
        except httpx.RequestError as exc:
            raise ExternalServiceError(f'Adzuna request failed: {exc}') from exc
