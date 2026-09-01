from app.agents.report_agent import REPORT_SECTIONS, build_final_report, run_report_agent
from app.agents.state import initial_state


def _full_mock_state():
    state = initial_state(cv_id=7, user_id=3)
    state.update(
        {
            'cv_summary': 'Alex — Python FastAPI developer',
            'structured_cv': {'name': 'Alex', 'skills': ['Python', 'FastAPI']},
            'ats_score': 82,
            'ats_issues': [{'code': 'too_long', 'severity': 'low', 'message': 'Slightly long'}],
            'ranked_jobs': [
                {
                    'job_id': 1,
                    'score': 0.91,
                    'title': 'Backend Engineer',
                    'company': 'Nimbus',
                    'location': 'London',
                    'url': 'https://example.com/1',
                    'description': 'Python FastAPI',
                }
            ],
            'market_trends': {
                'job_count': 4,
                'sample_too_small': False,
                'top_skills': [{'skill': 'Python', 'mention_count': 4, 'pct_of_postings': 100.0}],
                'note': None,
            },
            'skill_gaps': [
                {
                    'skill': 'Kubernetes',
                    'priority': 'high',
                    'demand_pct': 75.0,
                    'mention_count': 3,
                    'reason': 'high demand',
                }
            ],
            'learning_roadmap': {
                'days_30': {'focus': 'Foundations', 'skills': ['Kubernetes'], 'resources': []},
                'days_60': {'focus': 'Practice', 'skills': ['Docker'], 'resources': []},
                'days_90': {'focus': 'Advanced', 'skills': ['AWS'], 'resources': []},
            },
            'warnings': [],
        }
    )
    return state


def test_report_includes_all_sections_from_full_state():
    report = build_final_report(_full_mock_state())
    for section in REPORT_SECTIONS:
        assert section in report
    assert report['cv_summary']['available'] is True
    assert report['cv_summary']['text'].startswith('Alex')
    assert report['ats']['score'] == 82
    assert report['top_matches']['count'] == 1
    assert report['market_trends']['available'] is True
    assert report['skill_gaps']['count'] == 1
    assert report['learning_roadmap']['available'] is True
    assert report['missing_sections'] == []
    assert report['meta']['complete'] is True
    # No re-derivation: job title comes from ranked_jobs as-is
    assert report['top_matches']['jobs'][0]['title'] == 'Backend Engineer'


def test_report_notes_missing_sections_without_fabricating():
    state = initial_state(cv_id=1)
    state['cv_summary'] = 'Sparse profile'
    report = build_final_report(state)
    assert 'ats' in report['missing_sections']
    assert 'top_matches' in report['missing_sections']
    assert 'market_trends' in report['missing_sections']
    assert 'skill_gaps' in report['missing_sections']
    assert 'learning_roadmap' in report['missing_sections']
    assert report['top_matches']['jobs'] == []
    assert report['meta']['complete'] is False
    # Does not invent market skills
    assert report['market_trends']['data'] is None


def test_report_agent_writes_final_report_to_state():
    state = _full_mock_state()
    update = run_report_agent(state)
    assert 'final_report' in update
    assert update['final_report']['meta']['complete'] is True
    assert update['node_log'][-1]['node'] == 'report_agent'
    assert update['status'] == 'running'


def test_empty_skill_gaps_list_is_available_not_missing():
    state = _full_mock_state()
    state['skill_gaps'] = []  # computed, genuinely no gaps
    report = build_final_report(state)
    assert 'skill_gaps' not in report['missing_sections']
    assert report['skill_gaps']['available'] is True
    assert report['skill_gaps']['count'] == 0
