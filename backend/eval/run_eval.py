"""RAG evaluation runner.

Runs the golden dataset end-to-end (retrieve → generate → measure) and prints
a metrics table. Results are also written to a gitignored JSON file.

Usage (from ``backend/``)::

    python -m eval.run_eval                     # stub embeddings + stub generation
    python -m eval.run_eval --real-embeddings   # BGE embeddings (stub generation)
    python -m eval.run_eval --live              # live LLM generation
    python -m eval.run_eval --live --judge      # + optional LLM-as-judge
"""

from __future__ import annotations

import argparse
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.clients.llm_client import StubClient, get_llm_client
from app.core.config import settings
from app.db import Base
from app.services.faiss_store import reset_stores
from app.services.rag_pipeline import RagPipeline
from app.services.retrieval_service import RetrievalService, ensure_resource_index

from eval.citation import evaluate_citations
from eval.dataset import load_golden_dataset
from eval.groundedness import deterministic_groundedness
from eval.judge import judge_answer
from eval.metrics import document_keys, mrr, precision_at_k, recall_at_k

DEFAULT_K = 5
RESULTS_DIR = Path(__file__).with_name('results')

# Fixed seed corpus for job-retrieval cases (stable external_ids).
JOB_SPECS = [
    ('Backend Engineer', 'Python FastAPI PostgreSQL Docker', 'eval-backend'),
    ('API Developer', 'Python FastAPI REST SQL', 'eval-api'),
    ('Data Engineer', 'Python Spark Airflow SQL warehouse', 'eval-data'),
    ('Frontend Engineer', 'React TypeScript Vite Tailwind', 'eval-frontend'),
]


def _seed_jobs(db: Any) -> None:
    for title, description, external_id in JOB_SPECS:
        db.add(
            models.JobPosting(
                title=title,
                description=description,
                company='EvalCo',
                external_id=external_id,
                source='mock',
            )
        )
    db.commit()


def _real_embeddings_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        return True
    except Exception:
        return False


def _mode_label(real_embeddings: bool, live: bool) -> dict[str, str]:
    if real_embeddings:
        embeddings = (
            f'real ({settings.embedding_model})'
            if _real_embeddings_available()
            else 'real requested (sentence-transformers unavailable -> stub fallback)'
        )
    else:
        embeddings = 'stub (deterministic hash)'
    return {
        'embeddings': embeddings,
        'generation': 'stub' if not live else f'live ({settings.llm_provider or "?"})',
        'judge': 'disabled',
    }


def _run_case(
    case: dict[str, Any],
    rag: RagPipeline,
    *,
    k: int,
    judge: bool,
) -> dict[str, Any]:
    result = rag.run(
        case['query'],
        task=case['task'],
        profile='Software engineer',
        top_k=k,
        sources=case['sources'],
    )

    items = result.context_items
    item_dicts = [i.model_dump() for i in items]
    keys = document_keys(item_dicts)
    relevant = set(case['relevant_ids'])

    citation = evaluate_citations(result.answer, items)
    groundedness = deterministic_groundedness(
        result.answer,
        items,
        empty_context=result.empty_context,
    )

    judgement = None
    if judge:
        judgement = judge_answer(
            case['query'],
            result.answer,
            '\n\n'.join(f'[{i.source}:{i.id}] {i.text}' for i in items),
        )

    return {
        'id': case['id'],
        'query': case['query'],
        'task': case['task'],
        'sources': case['sources'],
        'relevant_ids': case['relevant_ids'],
        'retrieved': keys,
        'empty_context': result.empty_context,
        'precision@k': precision_at_k(keys, relevant, k),
        'recall@k': recall_at_k(keys, relevant, k),
        'mrr': mrr(keys, relevant),
        'citation': citation,
        'groundedness': groundedness,
        'judge': judgement,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(values: list[float]) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    accuracies = [r['citation']['accuracy'] for r in rows if r['citation']['accuracy'] is not None]
    grounded = [r for r in rows if not r['empty_context']]
    grounded_ok = [r for r in grounded if r['groundedness']['grounded']]
    return {
        'cases': len(rows),
        'mean_precision@k': mean([r['precision@k'] for r in rows]),
        'mean_recall@k': mean([r['recall@k'] for r in rows]),
        'mean_mrr': mean([r['mrr'] for r in rows]),
        'citation_accuracy': mean(accuracies),
        'grounded_rate': round(len(grounded_ok) / len(grounded), 4) if grounded else 0.0,
    }


def _print_table(mode: dict[str, str], rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    print('\n=== RAG evaluation ===')
    print(f"embeddings : {mode['embeddings']}")
    print(f"generation : {mode['generation']}")
    print(f"judge      : {mode['judge']}")
    print(f"{'case':<18} {'P@k':>6} {'R@k':>6} {'MRR':>6} {'cite':>6} {'grounded':>9}")
    for r in rows:
        cite = r['citation']['accuracy']
        cite_s = '-' if cite is None else f'{cite:.2f}'
        g = r['groundedness']
        g_s = 'hedge' if g['empty_context'] else ('yes' if g['grounded'] else 'no')
        print(
            f"{r['id']:<18} {r['precision@k']:>6.3f} {r['recall@k']:>6.3f} "
            f"{r['mrr']:>6.3f} {cite_s:>6} {g_s:>9}"
        )
    print('\n--- summary ---')
    print(f"cases               : {summary['cases']}")
    print(f"mean precision@k    : {summary['mean_precision@k']}")
    print(f"mean recall@k       : {summary['mean_recall@k']}")
    print(f"mean MRR            : {summary['mean_mrr']}")
    print(f"citation accuracy   : {summary['citation_accuracy']}")
    print(f"grounded rate       : {summary['grounded_rate']}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description='RAG evaluation runner')
    parser.add_argument('--real-embeddings', action='store_true', help='use BGE embeddings (default: stub)')
    parser.add_argument('--live', action='store_true', help='use live LLM generation (default: stub)')
    parser.add_argument('--judge', action='store_true', help='run optional LLM-as-judge (requires --live)')
    parser.add_argument('--k', type=int, default=DEFAULT_K, help='top-k for retrieval (default 5)')
    parser.add_argument('--out', type=str, default=None, help='results JSON path')
    args = parser.parse_args()

    # Isolate the index so the run never touches the persisted dev index.
    settings.faiss_index_dir = tempfile.mkdtemp(prefix='eval-faiss-')
    if args.real_embeddings and not _real_embeddings_available():
        print('NOTE: sentence-transformers is not installed; using stub embeddings.')
        settings.embedding_use_stub = True
    elif args.real_embeddings:
        settings.embedding_use_stub = False
        settings.llm_provider = 'gemini'  # ensure embed() uses the model, not stub
    else:
        settings.embedding_use_stub = True
    reset_stores()

    generation_client = get_llm_client() if args.live else StubClient()
    mode = _mode_label(args.real_embeddings, args.live)
    if args.judge:
        mode['judge'] = 'enabled (LLM-as-judge)'

    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        _seed_jobs(db)
        retrieval = RetrievalService(db)
        ensure_resource_index(store=retrieval.resources_store)
        rag = RagPipeline(db, retrieval=retrieval, llm=generation_client)

        cases = load_golden_dataset()
        rows = [_run_case(case, rag, k=args.k, judge=args.judge) for case in cases]
        summary = _summarize(rows)
        _print_table(mode, rows, summary)

        payload = {
            'mode': mode,
            'k': args.k,
            'embedding_model': settings.embedding_model,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': summary,
            'results': rows,
        }
        out_path = Path(args.out) if args.out else (RESULTS_DIR / 'last_run.json')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        print(f'Results written to {out_path}')
    finally:
        db.close()
        reset_stores()


if __name__ == '__main__':
    main()
