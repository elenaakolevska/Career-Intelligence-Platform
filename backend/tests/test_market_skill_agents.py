from app.agents.market_trends_agent import analyze_market_trends, run_market_trends_agent
from app.agents.skill_gap_agent import SKILL_GAP_KEYS, compute_skill_gaps, run_skill_gap_agent
from app.agents.skill_utils import canonicalize_skill, extract_skills_from_text, skills_match
from app.agents.state import initial_state


def test_extract_skills_from_job_text():
    text = 'We need Python, FastAPI, PostgreSQL and Kubernetes experience. Docker a plus.'
    skills = extract_skills_from_text(text)
    assert 'Python' in skills
    assert 'FastAPI' in skills
    assert 'PostgreSQL' in skills
    assert 'Kubernetes' in skills
    assert 'Docker' in skills


def test_market_trends_quantifies_pct_and_ranks():
    jobs = [
        {'title': 'Backend', 'description': 'Python FastAPI PostgreSQL Docker'},
        {'title': 'API Eng', 'description': 'Python FastAPI Redis'},
        {'title': 'Platform', 'description': 'Python Kubernetes Docker AWS'},
        {'title': 'Data', 'description': 'Python Spark SQL'},
    ]
    trends = analyze_market_trends(jobs)
    assert trends['job_count'] == 4
    assert trends['sample_too_small'] is False
    assert trends['top_skills']
    # Python in all 4 → 100%
    python = next(s for s in trends['top_skills'] if s['skill'] == 'Python')
    assert python['mention_count'] == 4
    assert python['pct_of_postings'] == 100.0
    # Ranked by frequency: Python first
    assert trends['top_skills'][0]['skill'] == 'Python'
    fastapi = next(s for s in trends['top_skills'] if s['skill'] == 'FastAPI')
    assert fastapi['pct_of_postings'] == 50.0


def test_market_trends_small_sample_flagged():
    jobs = [
        {'title': 'Eng', 'description': 'Python Docker'},
        {'title': 'Eng 2', 'description': 'Python AWS'},
    ]
    trends = analyze_market_trends(jobs)
    assert trends['sample_too_small'] is True
    assert trends['note'] and 'indicative' in trends['note'].lower()


def test_market_trends_empty_jobs():
    trends = analyze_market_trends([])
    assert trends['job_count'] == 0
    assert trends['top_skills'] == []
    assert trends['sample_too_small'] is True


def test_skill_gap_excludes_owned_skills_semantically():
    trends = {
        'job_count': 4,
        'sample_too_small': False,
        'top_skills': [
            {'skill': 'Python', 'mention_count': 4, 'pct_of_postings': 100.0},
            {'skill': 'Kubernetes', 'mention_count': 3, 'pct_of_postings': 75.0},
            {'skill': 'PostgreSQL', 'mention_count': 2, 'pct_of_postings': 50.0},
            {'skill': 'AWS', 'mention_count': 2, 'pct_of_postings': 50.0},
        ],
    }
    # Candidate has python + postgres alias
    gaps = compute_skill_gaps(
        candidate_skills=['python', 'postgres', 'SQL'],
        market_trends=trends,
    )
    gap_names = {g['skill'] for g in gaps}
    assert 'Python' not in gap_names
    assert 'PostgreSQL' not in gap_names
    assert 'Kubernetes' in gap_names
    assert 'AWS' in gap_names
    # Kubernetes higher demand → higher priority
    k8s = next(g for g in gaps if g['skill'] == 'Kubernetes')
    assert k8s['priority'] == 'high'
    for g in gaps:
        for key in SKILL_GAP_KEYS:
            assert key in g


def test_skill_gap_known_fixture_exact_list():
    """Known fixture → exact prioritized gap list for Learning Path Agent."""
    trends = {
        'job_count': 5,
        'sample_too_small': False,
        'top_skills': [
            {'skill': 'Python', 'mention_count': 5, 'pct_of_postings': 100.0},
            {'skill': 'Docker', 'mention_count': 4, 'pct_of_postings': 80.0},
            {'skill': 'Kubernetes', 'mention_count': 3, 'pct_of_postings': 60.0},
            {'skill': 'Terraform', 'mention_count': 2, 'pct_of_postings': 40.0},
            {'skill': 'GraphQL', 'mention_count': 1, 'pct_of_postings': 20.0},
        ],
    }
    gaps = compute_skill_gaps(
        candidate_skills=['Python', 'FastAPI', 'k8s'],  # k8s ≡ Kubernetes
        market_trends=trends,
    )
    # Exact ordered list (priority desc, then demand_pct desc)
    assert [g['skill'] for g in gaps] == ['Docker', 'Terraform', 'GraphQL']
    assert [g['priority'] for g in gaps] == ['high', 'medium', 'low']
    assert gaps[0]['demand_pct'] == 80.0
    assert gaps[1]['demand_pct'] == 40.0
    assert gaps[2]['demand_pct'] == 20.0
    assert all(set(SKILL_GAP_KEYS).issubset(g.keys()) for g in gaps)


def test_skill_gap_reads_skills_from_cv_summary():
    state = initial_state(cv_id=1)
    state['structured_cv'] = {'skills': []}  # empty structured list
    state['cv_summary'] = 'Candidate: Ada\nSkills: Python, FastAPI, Docker'
    state['market_trends'] = {
        'job_count': 3,
        'sample_too_small': False,
        'top_skills': [
            {'skill': 'Python', 'mention_count': 3, 'pct_of_postings': 100.0},
            {'skill': 'Kubernetes', 'mention_count': 2, 'pct_of_postings': 66.7},
            {'skill': 'Docker', 'mention_count': 2, 'pct_of_postings': 66.7},
        ],
    }
    update = run_skill_gap_agent(state)
    names = {g['skill'] for g in update['skill_gaps']}
    assert 'Python' not in names
    assert 'Docker' not in names
    assert 'Kubernetes' in names


def test_skills_match_aliases():
    owned = {canonicalize_skill('k8s'), canonicalize_skill('js')}
    assert skills_match('Kubernetes', owned)
    assert skills_match('JavaScript', owned)
    assert not skills_match('Rust', owned)


def test_skill_gap_agent_state_integration():
    state = initial_state(cv_id=1)
    state['structured_cv'] = {'skills': ['Python', 'FastAPI']}
    state['ranked_jobs'] = [
        {'title': 'A', 'description': 'Python FastAPI Kubernetes'},
        {'title': 'B', 'description': 'Python Kubernetes Docker'},
        {'title': 'C', 'description': 'Python Kubernetes AWS'},
    ]
    state.update(run_market_trends_agent(state))
    update = run_skill_gap_agent(state)
    assert 'skill_gaps' in update
    names = {g['skill'] for g in update['skill_gaps']}
    assert 'Python' not in names
    assert 'FastAPI' not in names
    assert 'Kubernetes' in names
    assert update['node_log'][-1]['node'] == 'skill_gap_agent'


def test_analysis_graph_includes_trends_and_gaps(tmp_path, monkeypatch):
    import json

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app import models
    from app.agents.graph import run_analysis_graph
    from app.agents.workflow import CAREER_GRAPH_ORDER
    from app.db import Base
    from app.services.embedding_pipeline import embed_jobs_batch
    from app.services.faiss_store import reset_stores
    from app.services.user_service import UserService
    from app.core.config import settings

    monkeypatch.setattr(settings, 'embedding_use_stub', True)
    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    monkeypatch.setattr(settings, 'faiss_index_dir', str(tmp_path / 'faiss'))
    monkeypatch.setattr(settings, 'rerank_enabled', False)
    # Hermetic: never enter live-Adzuna mode, which filters out mock sources.
    monkeypatch.setattr(settings, 'adzuna_app_id', None)
    monkeypatch.setattr(settings, 'adzuna_use_mock', True)
    reset_stores()

    engine = create_engine(
        'sqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        user = UserService(db).create_user(email='trends@example.com')
        cv = models.CVProfile(
            user_id=user.id,
            status='completed',
            raw_text='Python FastAPI developer',
            summary='Python FastAPI developer',
            structured_data=json.dumps(
                {
                    'name': 'Alex',
                    'skills': ['Python', 'FastAPI'],
                    'summary': 'Python FastAPI developer',
                }
            ),
        )
        db.add(cv)
        jobs = [
            models.JobPosting(
                title='Backend',
                description='Python FastAPI Kubernetes Docker',
                company='A',
                external_id='t1',
                source='mock',
            ),
            models.JobPosting(
                title='Platform',
                description='Python Kubernetes AWS Docker',
                company='B',
                external_id='t2',
                source='mock',
            ),
            models.JobPosting(
                title='API',
                description='Python FastAPI PostgreSQL',
                company='C',
                external_id='t3',
                source='mock',
            ),
        ]
        for job in jobs:
            db.add(job)
        db.commit()
        db.refresh(cv)
        for job in jobs:
            db.refresh(job)
        embed_jobs_batch([j.id for j in jobs], db)

        result = run_analysis_graph(db, cv_id=cv.id, user_id=user.id)
        assert result['status'] == 'completed'
        assert result['market_trends'] and result['market_trends']['top_skills']
        assert isinstance(result['skill_gaps'], list)
        nodes = [e['node'] for e in result['node_log']]
        # Full career order (may include skipped markers only on halt paths)
        assert nodes == list(CAREER_GRAPH_ORDER)
        assert result.get('learning_roadmap')
        assert result.get('final_report')
        assert result['final_report']['cv_summary']['available'] is True
        for key in ('days_30', 'days_60', 'days_90'):
            assert key in result['learning_roadmap']
    finally:
        db.close()
        reset_stores()
