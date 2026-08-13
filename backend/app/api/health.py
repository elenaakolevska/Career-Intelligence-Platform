from fastapi import APIRouter, Response
from app.core.config import settings
from app.db import get_engine

router = APIRouter(prefix='/health', tags=['health'])


@router.get('')
def health() -> dict:
    return {'status': 'ok'}


@router.get('/ready')
def readiness(response: Response) -> dict:
    results: dict = {}
    ok = True
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute('SELECT 1')
        results['db'] = 'ok'
    except Exception:
        results['db'] = 'unreachable'
        ok = False
    try:
        import redis

        r = redis.from_url(settings.redis_url, socket_connect_timeout=1)
        r.ping()
        results['redis'] = 'ok'
    except Exception:
        results['redis'] = 'unreachable'
        ok = False
    status = 'ok' if ok else 'degraded'
    response.status_code = 200 if ok else 503
    return {'status': status, 'checks': results}
