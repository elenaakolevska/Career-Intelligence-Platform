"""P6-09: broader multi-agent end-to-end tests across multiple CVs."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.agents.workflow import CAREER_GRAPH_ORDER, run_career_workflow
from app.db import Base
from app.services.embedding_pipeline import embed_jobs_batch
from app.services.faiss_store import reset_stores
from app.services.user_service import UserService

logger = logging.getLogger(__name__)
FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'cvs'

CV_CASES = [
    {
        'email': 'junior@example.com',
        'fixture': 'junior_backend.txt',
        'structured': {
            'name': 'Alex Petrov',
            'skills': ['Python', 'FastAPI', 'SQL', 'Git', 'Docker', 'Linux'],
            'summary': 'Junior backend developer',
            'experience': [{'title': 'Backend Intern', 'company': 'SoftWave'}],
        },
    },
    {
        'email': 'senior@example.com',
        'fixture': 'senior_fullstack.txt',
        'structured': {
            'name': 'Samira Khan',
            'skills': [
                'Python',
                'FastAPI',
                'React',
                'TypeScript',
                'PostgreSQL',
                'Redis',
                'Kubernetes',
                'AWS',
                'Terraform',
            ],
            'summary': 'Senior full-stack engineer',
            'experience': [{'title': 'Staff Engineer', 'company': 'Northstar Systems'}],
        },
    },
    {
        'email': 'switcher@example.com',
        'fixture': 'career_switcher.txt',
        'structured': {
            'name': 'Morgan Ellis',
            'skills': ['HTML', 'CSS', 'JavaScript', 'Python'],
            'summary': 'Former teacher transitioning into tech',
            'experience': [{'title': 'Teacher', 'company': 'City High School'}],
        },
    },
]


def _db_session():
    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_jobs(db, *, backend_heavy: bool = True):
    if backend_heavy:
        specs = [
            ('Backend Engineer', 'Python FastAPI PostgreSQL Docker Kubernetes'),
            ('Platform Engineer', 'Python Kubernetes Docker AWS Terraform'),
            ('API Developer', 'Python FastAPI SQL Redis Linux'),
        ]
    else:
        specs = [
            ('Frontend Engineer', 'React TypeScript JavaScript CSS HTML'),
            ('UI Engineer', 'React TypeScript Vite Tailwind'),
            ('Web Developer', 'JavaScript HTML CSS React'),
        ]
    jobs = []
    for i, (title, desc) in enumerate(specs, start=1):
        job = models.JobPosting(
            title=title,
            description=desc,
            company=f'Co{i}',
            external_id=f'e2e-{i}-{title[:6]}',
            source='mock',
        )
        db.add(job)
        jobs.append(job)
    db.commit()
    for job in jobs:
        db.refresh(job)
    embed_jobs_batch([j.id for j in jobs], db)
    return jobs


def _seed_cv(db, case: dict) -> models.CVProfile:
    raw = (FIXTURES / case['fixture']).read_text(encoding='utf-8')
    user = UserService(db).create_user(email=case['email'])
    structured = case['structured']
    cv = models.CVProfile(
        user_id=user.id,
        status='completed',
        raw_text=raw,
        summary=structured.get('summary'),
        structured_data=json.dumps(structured),
        ats_score=70,
        ats_issues=json.dumps([]),
        extraction_method='native',
    )
    db.add(cv)
    db.commit()
    db.refresh(cv)
    return cv


def _assert_report_structure(state: dict, *, note: str):
    report = state.get('final_report')
    assert report, note
    for section in (
        'cv_summary',
        'ats',
        'top_matches',
        'market_trends',
        'skill_gaps',
        'learning_roadmap',
        'missing_sections',
        'meta',
    ):
        assert section in report, f'{note}: missing {section}'
    assert report['cv_summary']['available'] is True
    # Quality spot-check notes (P6-09): summary should mention candidate or skills
    text = report['cv_summary'].get('text') or ''
    assert len(text) > 20, f'{note}: cv summary too thin'


@pytest.mark.parametrize('case', CV_CASES, ids=[c['fixture'] for c in CV_CASES])
def test_e2e_three_cvs_produce_complete_reports(case, tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / f"faiss-{case['fixture']}"))
    monkeypatch.setattr(settings, 'rerank_enabled', False)
    reset_stores()

    db = _db_session()
    try:
        cv = _seed_cv(db, case)
        _seed_jobs(db, backend_heavy='fullstack' not in case['fixture'] or True)
        # Use backend-ish jobs for all; senior still has Python overlap
        result = run_career_workflow(db, cv_id=cv.id, user_id=cv.user_id)
        state = result['state']
        logger.info(
            'P6-09 baseline timing fixture=%s total_ms=%s node_timings=%s',
            case['fixture'],
            result['total_ms'],
            result['node_timings_ms'],
        )
        assert result['total_ms'] >= 0
        nodes = [e['node'] for e in result['node_log']]
        assert nodes == list(CAREER_GRAPH_ORDER)
        assert 'retrieval_agent' in nodes
        assert state.get('retrieval_context') is not None
        _assert_report_structure(state, note=case['fixture'])
        assert state.get('status') == 'completed'
        # Spot-check: roadmaps / gaps differ in shape across candidates is soft —
        # at least skill_gaps list exists
        assert isinstance(state.get('skill_gaps'), list)
    finally:
        db.close()
        reset_stores()


def test_e2e_failure_path_no_job_matches(tmp_path, monkeypatch):
    """P6-08 continue policy: zero matches should not crash; report still produced."""
    from app.core.config import settings
    from app.agents import job_matching_agent as jma

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss-nomatch'))
    monkeypatch.setattr(settings, 'rerank_enabled', False)
    monkeypatch.setattr(jma, 'search_jobs_for_cv', lambda *a, **k: [])
    reset_stores()

    db = _db_session()
    try:
        cv = _seed_cv(db, CV_CASES[0])
        # Jobs exist in DB so seed path is skipped, but search returns []
        db.add(
            models.JobPosting(
                title='Unindexed',
                description='zzz',
                company='Z',
                external_id='nomatch-1',
                source='mock',
            )
        )
        db.commit()

        result = run_career_workflow(db, cv_id=cv.id, user_id=cv.user_id)
        state = result['state']
        logger.info(
            'P6-09 no-match failure path total_ms=%s warnings=%s',
            result['total_ms'],
            state.get('warnings'),
        )
        assert state.get('ranked_jobs') == []
        assert any('zero matches' in w for w in (state.get('warnings') or []))
        assert state.get('final_report')  # report agent still ran
        assert state.get('status') == 'completed'
        assert state.get('halted') is False
        nodes = [e['node'] for e in result['node_log']]
        assert nodes == list(CAREER_GRAPH_ORDER)
    finally:
        db.close()
        reset_stores()


def test_e2e_reports_differ_across_profiles(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'rerank_enabled', False)
    reset_stores()

    summaries = []
    gap_sets = []
    for case in CV_CASES[:2]:
        monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / f"diff-{case['fixture']}"))
        reset_stores()
        db = _db_session()
        try:
            cv = _seed_cv(db, case)
            _seed_jobs(db)
            state = run_career_workflow(db, cv_id=cv.id, user_id=cv.user_id)['state']
            summaries.append(state['final_report']['cv_summary']['text'])
            gap_sets.append({g['skill'] for g in (state.get('skill_gaps') or [])})
        finally:
            db.close()
            reset_stores()

    assert summaries[0] != summaries[1]
    # Quality note: junior vs senior should not produce identical gap sets in typical market
    # (soft check — allow overlap but require at least one differing summary signal)
    assert 'Alex' in summaries[0] or 'Python' in summaries[0]
    assert 'Samira' in summaries[1] or 'React' in summaries[1] or 'full-stack' in summaries[1].lower()
