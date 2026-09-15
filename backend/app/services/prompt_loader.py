"""Prompt loading and placeholder substitution."""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings

NO_CONTEXT_MARKERS = (
    'Insufficient retrieved context to analyze market trends.',
    'Insufficient retrieved context to determine skill gaps.',
    'Insufficient retrieved context to build a learning roadmap.',
    'Insufficient retrieved context to explain this gap.',
)

RAG_PROMPT_FILES = {
    'market_trends': 'market_trends_prompt.txt',
    'skill_gap': 'skill_gap_prompt.txt',
    'learning_roadmap': 'learning_roadmap_prompt.txt',
    'gap_narrative': 'gap_narrative_prompt.txt',
}


def _prompts_root() -> Path:
    configured = Path(settings.prompts_dir)
    candidates = [
        configured if configured.is_absolute() else (Path.cwd() / configured).resolve(),
        Path('/prompts'),
        Path.cwd().parent / 'prompts',
        Path(__file__).resolve().parents[3] / 'prompts',  # repo root when running from backend/
        Path(__file__).resolve().parents[2] / 'prompts',  # backend/prompts fallback
    ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_dir():
            return resolved
    # Fall back to first candidate for a clear FileNotFoundError path
    return candidates[0]


def load_prompt(name: str) -> str:
    path = _prompts_root() / name
    if not path.exists():
        raise FileNotFoundError(f'Prompt not found: {path}')
    return path.read_text(encoding='utf-8')


def render_prompt(name: str, **placeholders: str) -> str:
    """Load a prompt file and substitute ``{{KEY}}`` placeholders."""
    template = load_prompt(name)
    rendered = template
    for key, value in placeholders.items():
        rendered = rendered.replace('{{' + key + '}}', value if value is not None else '')
    return rendered


def render_cv_extraction_prompt(cv_text: str) -> str:
    return render_prompt('cv_extraction_prompt.txt', CV_TEXT=cv_text.strip())


def render_interview_question_prompt(
    *,
    target_role: str,
    difficulty: str,
    seniority_context: str,
    previous_questions: str,
    variation_seed: str,
) -> str:
    return render_prompt(
        'interview_question_prompt.txt',
        TARGET_ROLE=target_role,
        DIFFICULTY=difficulty,
        SENIORITY_CONTEXT=seniority_context,
        PREVIOUS_QUESTIONS=previous_questions,
        VARIATION_SEED=variation_seed,
    )


def render_interview_eval_prompt(
    *,
    target_role: str,
    difficulty: str,
    question: str,
    answer: str,
) -> str:
    return render_prompt(
        'interview_eval_prompt.txt',
        TARGET_ROLE=target_role,
        DIFFICULTY=difficulty,
        QUESTION=question,
        ANSWER=answer,
    )


def render_rag_prompt(
    task: str,
    *,
    context: str,
    profile: str,
    question: str,
) -> str:
    filename = RAG_PROMPT_FILES.get(task)
    if not filename:
        raise ValueError(f'Unknown RAG task: {task}. Expected one of {sorted(RAG_PROMPT_FILES)}')
    return render_prompt(
        filename,
        CONTEXT=context or '',
        PROFILE=profile or '',
        QUESTION=question or '',
    )
