"""WebSocket message helpers for the interview simulator (P7-04)."""

from __future__ import annotations

import json
from typing import Any

from app.schemas.interview import InterviewRead


def session_payload(session: InterviewRead) -> dict[str, Any]:
    return session.model_dump(mode='json')


def ws_message(msg_type: str, **payload: Any) -> dict[str, Any]:
    return {'type': msg_type, **payload}


def ws_error(code: str, detail: str, **extra: Any) -> dict[str, Any]:
    return ws_message('error', code=code, detail=detail, **extra)


def parse_client_message(raw: str | bytes) -> dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('WebSocket message must be a JSON object')
    msg_type = data.get('type')
    if not msg_type or not isinstance(msg_type, str):
        raise ValueError('WebSocket message requires a string "type" field')
    return data
