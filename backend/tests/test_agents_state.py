from app.agents import (
    STATE_FIELD_OWNERS,
    build_noop_graph,
    deserialize_state,
    initial_state,
    run_noop_graph,
    serialize_state,
)
from app.agents.state import CareerGraphState


def test_state_covers_agent_fields_and_owners():
    required = {
        'cv_id',
        'cv_summary',
        'structured_cv',
        'ats_score',
        'ranked_jobs',
        'retrieval_context',
        'market_trends',
        'skill_gaps',
        'learning_roadmap',
        'final_report',
        'errors',
        'node_log',
        'status',
    }
    annotations = set(CareerGraphState.__annotations__)
    assert required.issubset(annotations)
    for field in required:
        assert field in STATE_FIELD_OWNERS
    assert STATE_FIELD_OWNERS['cv_summary'] == 'cv_agent'
    assert STATE_FIELD_OWNERS['ranked_jobs'] == 'job_matching_agent'
    assert STATE_FIELD_OWNERS['retrieval_context'] == 'retrieval_agent'
    assert STATE_FIELD_OWNERS['final_report'] == 'report_agent'


def test_state_is_json_serializable():
    state = initial_state(cv_id=7, user_id=3)
    state['cv_summary'] = 'Backend engineer'
    state['skill_gaps'] = [{'skill': 'Kubernetes', 'priority': 'high'}]
    payload = serialize_state(state)
    restored = deserialize_state(payload)
    assert restored['cv_id'] == 7
    assert restored['cv_summary'] == 'Backend engineer'
    assert restored['skill_gaps'][0]['skill'] == 'Kubernetes'


def test_noop_graph_compiles_and_runs():
    graph = build_noop_graph()
    assert graph is not None
    result = run_noop_graph(cv_id=42, user_id=1)
    assert result['cv_id'] == 42
    assert result['status'] == 'completed'
    nodes = [entry['node'] for entry in result.get('node_log') or []]
    assert nodes == ['noop_bootstrap', 'noop_finish']
