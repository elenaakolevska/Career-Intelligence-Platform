"""Interview WebSocket handler (P7-04) — chat turns over a persistent socket."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.db import SessionLocal
from app.interview.ws_protocol import parse_client_message, session_payload, ws_error, ws_message
from app.services.interview_service import InterviewService

logger = logging.getLogger(__name__)


async def _send(websocket: WebSocket, payload: dict[str, Any]) -> None:
    if websocket.client_state != WebSocketState.CONNECTED:
        return
    await websocket.send_json(payload)


def _with_service(fn: Callable[[InterviewService], Any]) -> Any:
    """Run a sync InterviewService call on a fresh DB session (thread-safe)."""
    db = SessionLocal()
    try:
        return fn(InterviewService(db))
    finally:
        db.close()


async def handle_interview_websocket(websocket: WebSocket, session_id: int) -> None:
    """
    Protocol (JSON):

    Client → server:
      {"type": "next_question"}
      {"type": "answer", "answer": "..."}
      {"type": "complete", "overall_feedback": "...?"}
      {"type": "abandon"}
      {"type": "ping"}
      {"type": "get_state"}

    Server → client:
      {"type": "connected"|"state"|"question"|"feedback"|"completed"|"abandoned"|"pong"|"error", ...}

    Disconnect/reconnect is safe: state is loaded from DB on every connect.
    Mid-session failures are sent as {"type":"error", ...} rather than hanging.
    Heavy sync work (LLM question/eval) runs in a worker thread so pings stay alive.
    """
    await websocket.accept()

    try:
        read = await asyncio.to_thread(
            _with_service, lambda svc: svc._to_read(svc.get_session(session_id)) if svc.get_session(session_id) else None
        )
        if not read:
            await _send(websocket, ws_error('not_found', f'Interview session {session_id} not found'))
            await websocket.close(code=4404)
            return

        await _send(
            websocket,
            ws_message(
                'connected',
                session_id=session_id,
                session=session_payload(read),
                resumable=read.status not in {'abandoned'},
            ),
        )

        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info('interview ws disconnected session_id=%s', session_id)
                break

            try:
                msg = parse_client_message(raw)
            except (ValueError, TypeError) as exc:
                await _send(websocket, ws_error('bad_message', str(exc)))
                continue

            msg_type = msg['type'].strip().lower()
            try:
                row_status = await asyncio.to_thread(
                    _with_service,
                    lambda svc: (svc.get_session(session_id).status if svc.get_session(session_id) else None),
                )
                if row_status is None:
                    await _send(websocket, ws_error('not_found', 'Interview session not found'))
                    await websocket.close(code=4404)
                    break

                if msg_type == 'ping':
                    await _send(websocket, ws_message('pong'))
                    continue

                if msg_type == 'get_state':
                    state_read = await asyncio.to_thread(
                        _with_service,
                        lambda svc: svc._to_read(svc.get_session(session_id)),
                    )
                    await _send(
                        websocket,
                        ws_message('state', session=session_payload(state_read)),
                    )
                    continue

                if row_status in {'completed', 'abandoned'} and msg_type not in {
                    'get_state',
                    'ping',
                }:
                    await _send(
                        websocket,
                        ws_error(
                            'session_closed',
                            f'Session is {row_status}; reconnect for read-only state only',
                            status=row_status,
                        ),
                    )
                    continue

                if msg_type == 'next_question':
                    await _send(websocket, ws_message('status', detail='Generating question…'))
                    result = await asyncio.to_thread(
                        _with_service, lambda svc: svc.generate_next_question(session_id)
                    )
                    if result is None:
                        await _send(websocket, ws_error('not_found', 'Interview session not found'))
                        continue
                    turn = result.history[-1] if result.history else None
                    await _send(
                        websocket,
                        ws_message(
                            'question',
                            question=result.current_question or (turn.question if turn else None),
                            turn_index=turn.turn_index if turn else None,
                            topics=turn.topics if turn else None,
                            difficulty=turn.difficulty if turn else result.difficulty,
                            session=session_payload(result),
                        ),
                    )
                    continue

                if msg_type == 'answer':
                    answer = str(msg.get('answer') or '').strip()
                    if not answer:
                        await _send(websocket, ws_error('validation', 'answer must be a non-empty string'))
                        continue
                    result = await asyncio.to_thread(
                        _with_service, lambda svc: svc.submit_answer(session_id, answer)
                    )
                    if result is None:
                        await _send(
                            websocket,
                            ws_error(
                                'no_pending_question',
                                'No pending question to answer — send next_question first',
                            ),
                        )
                        continue
                    turn = result.history[-1] if result.history else None
                    await _send(
                        websocket,
                        ws_message(
                            'feedback',
                            question=turn.question if turn else None,
                            answer=turn.answer if turn else answer,
                            score=turn.score if turn else None,
                            feedback=turn.feedback if turn else result.latest_feedback,
                            turn_index=turn.turn_index if turn else None,
                            running_score=result.running_score,
                            session=session_payload(result),
                        ),
                    )
                    continue

                if msg_type == 'complete':
                    feedback = msg.get('overall_feedback')
                    result = await asyncio.to_thread(
                        _with_service,
                        lambda svc: svc.complete_session(
                            session_id,
                            overall_feedback=str(feedback) if feedback is not None else None,
                        ),
                    )
                    if result is None:
                        await _send(websocket, ws_error('not_found', 'Interview session not found'))
                        continue
                    await _send(
                        websocket,
                        ws_message('completed', session=session_payload(result)),
                    )
                    await websocket.close(code=1000)
                    break

                if msg_type == 'abandon':
                    result = await asyncio.to_thread(
                        _with_service, lambda svc: svc.abandon_session(session_id)
                    )
                    if result is None:
                        await _send(websocket, ws_error('not_found', 'Interview session not found'))
                        continue
                    await _send(
                        websocket,
                        ws_message('abandoned', session=session_payload(result)),
                    )
                    await websocket.close(code=1000)
                    break

                await _send(
                    websocket,
                    ws_error(
                        'unknown_type',
                        f'Unsupported message type: {msg_type}',
                        supported=['next_question', 'answer', 'complete', 'abandon', 'ping', 'get_state'],
                    ),
                )
            except Exception as exc:  # noqa: BLE001 — surface to client, don't hang
                logger.exception('interview ws handler error session_id=%s', session_id)
                await _send(
                    websocket,
                    ws_error('internal_error', f'{type(exc).__name__}: {exc}'),
                )
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except Exception:  # pragma: no cover
                pass
