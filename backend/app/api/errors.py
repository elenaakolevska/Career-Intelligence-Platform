from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from app.core.exceptions import NotFoundError, ValidationError, ExternalServiceError

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.info('http error %s %s', exc.status_code, exc.detail)
    return JSONResponse({'error': 'http_error', 'detail': exc.detail}, status_code=exc.status_code)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.info('validation error %s', exc.errors())
    return JSONResponse({'error': 'validation_error', 'detail': exc.errors()}, status_code=422)


async def custom_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, NotFoundError) or isinstance(exc, ValidationError) or isinstance(exc, ExternalServiceError):
        status = getattr(exc, 'status_code', 500)
        name = exc.__class__.__name__
        logger.info('%s: %s', name, getattr(exc, 'detail', ''))
        return JSONResponse({'error': name, 'detail': getattr(exc, 'detail', '')}, status_code=status)
    logger.exception('Unhandled exception')
    return JSONResponse({'error': 'internal_server_error', 'detail': 'Internal server error'}, status_code=500)
