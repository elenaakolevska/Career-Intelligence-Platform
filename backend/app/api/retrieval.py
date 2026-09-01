from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.retrieval import ContentType, RetrievalResult
from app.services.retrieval_service import RetrievalService, index_resources

router = APIRouter(prefix='/retrieval', tags=['retrieval'])


@router.get('/', response_model=RetrievalResult)
def retrieve_context(
    q: str = Query(..., min_length=1, description='Natural-language retrieval query'),
    top_k: int = Query(default=5, ge=1, le=50),
    sources: list[ContentType] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Retrieve grounded context from FAISS across jobs and/or learning resources."""
    return RetrievalService(db).retrieve(q, top_k=top_k, sources=sources)


@router.post('/resources/reindex')
def reindex_resources():
    count = index_resources()
    return {'indexed': count, 'source': 'resources'}
