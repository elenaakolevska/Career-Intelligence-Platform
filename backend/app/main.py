from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging import configure_logging
from app.api.health import router as health_router
from app.api.users import router as users_router
from app.api.cv import router as cv_router
from app.api.jobs import router as jobs_router
from app.api.analysis import router as analysis_router
from app.api.interview import router as interview_router
from app.api import errors as error_handlers

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="AI Career Intelligence Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(health_router, prefix='/api/v1')
app.include_router(users_router, prefix='/api/v1')
app.include_router(cv_router, prefix='/api/v1')
app.include_router(jobs_router, prefix='/api/v1')
app.include_router(analysis_router, prefix='/api/v1')
app.include_router(interview_router, prefix='/api/v1')


@app.exception_handler(StarletteHTTPException)
async def http_exc(request, exc):
    return await error_handlers.http_exception_handler(request, exc)


@app.exception_handler(RequestValidationError)
async def validation_exc(request, exc):
    return await error_handlers.validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def generic_exc(request, exc):
    return await error_handlers.custom_exception_handler(request, exc)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "AI Career Intelligence Platform API"}
