from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.rag import RagRequest, RagResponse
from app.services.prompt_loader import RAG_PROMPT_FILES
from app.services.rag_pipeline import RagPipeline

router = APIRouter(prefix='/rag', tags=['rag'])


@router.post('/generate', response_model=RagResponse)
def generate_rag(body: RagRequest, db: Session = Depends(get_db)):
    if body.task not in RAG_PROMPT_FILES:
        raise HTTPException(status_code=400, detail=f'Unsupported task: {body.task}')
    return RagPipeline(db).run(
        body.query,
        task=body.task,
        profile=body.profile,
        top_k=body.top_k,
        sources=body.sources,
        cv_id=body.cv_id,
        include_prompt_preview=True,
    )


@router.get('/tasks')
def list_rag_tasks():
    return {'tasks': sorted(RAG_PROMPT_FILES.keys())}
