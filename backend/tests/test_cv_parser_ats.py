from pathlib import Path

import pytest

from app.schemas.cv import StructuredCV
from app.services.ats_scorer import score_ats
from app.services.cv_parser import (
    CVParserService,
    extract_json_payload,
    repair_json,
    validate_structured_cv,
)
from app.services.heuristic_cv_parser import heuristic_parse_cv
from app.services.prompt_loader import load_prompt, render_cv_extraction_prompt


FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'cvs'


def test_prompt_has_schema_and_few_shot():
    prompt = load_prompt('cv_extraction_prompt.txt')
    assert '"skills"' in prompt
    assert 'Few-shot' in prompt or 'few-shot' in prompt.lower() or 'Expected JSON' in prompt
    assert '{{CV_TEXT}}' in prompt
    assert 'NEVER invent' in prompt


def test_render_substitutes_cv_text():
    rendered = render_cv_extraction_prompt('HELLO_CV_BODY')
    assert 'HELLO_CV_BODY' in rendered
    assert '{{CV_TEXT}}' not in rendered


def test_json_repair_trailing_comma():
    raw = extract_json_payload('{"name": "Ada", "skills": ["Python",],}')
    data = repair_json(raw)
    assert data['name'] == 'Ada'
    assert data['skills'] == ['Python']


def test_validate_rejects_empty_profile():
    with pytest.raises(Exception):
        validate_structured_cv({'name': None, 'email': None, 'skills': [], 'experience': []})


def test_validate_flags_zero_skills_but_accepts_named_profile():
    structured = validate_structured_cv(
        {'name': 'Ada Lovelace', 'email': 'ada@example.com', 'skills': [], 'experience': []}
    )
    assert structured.name == 'Ada Lovelace'
    assert structured.skills == []


def test_parser_stub_uses_heuristic(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, 'llm_provider', 'stub')
    text = (FIXTURES / 'junior_backend.txt').read_text(encoding='utf-8')
    structured = CVParserService().parse(text)
    assert structured.email and 'alex.petrov' in structured.email
    assert any('Python' == s or 'python' in s.lower() for s in structured.skills)


def test_malformed_llm_output_is_repaired(monkeypatch):
    from app.core.config import settings
    from app.clients.llm_client import StubClient

    monkeypatch.setattr(settings, 'llm_provider', 'gemini')

    class BadThenGood(StubClient):
        def __init__(self):
            self.calls = 0

        def generate(self, prompt: str, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return 'Here you go:\n```json\n{"name": "Pat", "skills": ["Go",],}\n```'
            return '{"name": "Pat", "email": "pat@example.com", "skills": ["Go"], "experience": []}'

    parser = CVParserService(llm=BadThenGood(), max_attempts=2)
    structured = parser.parse('Pat\npat@example.com\nSkills\nGo')
    assert structured.name == 'Pat'
    assert 'Go' in structured.skills


def test_ats_differentiates_clean_and_problematic():
    clean = heuristic_parse_cv((FIXTURES / 'ats_clean.txt').read_text(encoding='utf-8'))
    bad = heuristic_parse_cv((FIXTURES / 'ats_problematic.txt').read_text(encoding='utf-8'))
    clean_score = score_ats((FIXTURES / 'ats_clean.txt').read_text(encoding='utf-8'), clean)
    bad_score = score_ats((FIXTURES / 'ats_problematic.txt').read_text(encoding='utf-8'), bad)
    assert clean_score.score > bad_score.score
    assert bad_score.issues
    assert isinstance(clean_score.score, int)


def test_fixtures_exist():
    assert (FIXTURES / 'junior_backend.txt').exists()
    assert (FIXTURES / 'senior_fullstack.txt').exists()
    assert (FIXTURES / 'README.md').exists()
