# AI Career Intelligence Platform

Monorepo for an AI career intelligence platform: CV analysis, semantic job matching, skill-gap detection, learning roadmaps, and interview simulation (FastAPI + React + LangGraph/RAG planned).

## Structure

- `backend/`: FastAPI application and services
- `frontend/`: React + Vite frontend
- `prompts/`: reusable LLM prompt templates
- `docs/`: architecture notes and task tracking

## Quick start

1. Copy `.env.example` to `.env` and adjust credentials (`LLM_PROVIDER=stub` works offline).
2. `docker compose up --build`
3. Open http://localhost:5173 (frontend) and http://localhost:8000/docs (API)

## Useful API routes

- `POST /api/v1/cv/upload` — PDF upload → extract → parse → ATS score
- `POST /api/v1/jobs/seed-mock` — load mock job market data + embeddings (includes MK + UK corpora)
- `POST /api/v1/jobs/fetch/{cv_id}` — Adzuna live jobs when `ADZUNA_USE_MOCK=false`, else mock (MK-preferring for MK CVs)
- `GET /api/v1/jobs/match/{cv_id}` — semantic job matches for a CV
- `POST /api/v1/analysis/run/{cv_id}` — full multi-agent career report
