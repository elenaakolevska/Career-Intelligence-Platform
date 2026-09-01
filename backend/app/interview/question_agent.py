"""Interview Question Agent (P7-02): role-specific technical questions via LLM."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.job_matching_agent import estimate_candidate_level
from app.clients.llm_client import LLMClient, StubClient, get_llm_client
from app.core.config import settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.interview.state import (
    InterviewGraphState,
    append_interview_node_log,
    append_turn,
)
from app.services.cv_parser import extract_json_payload, repair_json
from app.services.prompt_loader import render_prompt

logger = logging.getLogger(__name__)

DIFFICULTY_ORDER = ('junior', 'mid', 'senior')

# Role-keyword → technical question banks (stub / offline path). Keys are substrings.
_ROLE_QUESTION_BANKS: dict[str, dict[str, list[tuple[str, list[str]]]]] = {
    'java': {
        'junior': [
            (
                'In Java, what is the difference between an ArrayList and a LinkedList, '
                'and when would you choose one over the other for a {role} task?',
                ['collections', 'ArrayList', 'LinkedList'],
            ),
            (
                'Explain how the Java `equals` and `hashCode` contract works, and why it matters '
                'when storing domain objects in a HashMap for a {role} service.',
                ['equals', 'hashCode', 'HashMap'],
            ),
            (
                'What does the `synchronized` keyword do in Java, and describe one situation a '
                '{role} might need it when sharing state across threads.',
                ['concurrency', 'synchronized'],
            ),
        ],
        'mid': [
            (
                'How would you design a Spring Boot REST endpoint for a {role} that validates input, '
                'returns proper HTTP status codes, and handles domain exceptions cleanly?',
                ['Spring Boot', 'REST', 'validation'],
            ),
            (
                'Compare checked vs unchecked exceptions in Java. How would you structure error '
                'handling in a multi-layer {role} application?',
                ['exceptions', 'error handling'],
            ),
            (
                'Explain Spring dependency injection (constructor vs field). What tradeoffs matter '
                'for testability in a {role} codebase?',
                ['DI', 'Spring', 'testing'],
            ),
        ],
        'senior': [
            (
                'How would you evolve a monolithic Java service used by a {role} team toward '
                'modular boundaries without a big-bang rewrite?',
                ['architecture', 'modularity'],
            ),
            (
                'Describe how you would diagnose and mitigate a production JVM memory leak '
                'affecting a high-traffic {role} API.',
                ['JVM', 'observability', 'memory'],
            ),
            (
                'What consistency and failure tradeoffs would you consider when adding asynchronous '
                'messaging between Java services in a {role} platform?',
                ['messaging', 'consistency', 'distributed systems'],
            ),
        ],
    },
    'python': {
        'junior': [
            (
                'In Python, explain the difference between a list and a tuple, and when a {role} '
                'should prefer one for API request handling.',
                ['list', 'tuple', 'data structures'],
            ),
            (
                'What is a Python virtual environment, and why would a {role} use one when '
                'managing project dependencies?',
                ['venv', 'dependencies'],
            ),
            (
                'Explain how exceptions propagate in Python. Show how you would catch and log a '
                'database error in a {role} service without hiding the root cause.',
                ['exceptions', 'logging'],
            ),
        ],
        'mid': [
            (
                'How would you structure a FastAPI route for a {role} that uses Pydantic models, '
                'dependency injection, and clear 4xx/5xx responses?',
                ['FastAPI', 'Pydantic', 'HTTP'],
            ),
            (
                'Compare sync vs async I/O in Python for a {role} calling external APIs. When is '
                '`async` worth the complexity?',
                ['async', 'I/O', 'performance'],
            ),
            (
                'How would you write unit tests for a {role} service that talks to Postgres, '
                'keeping tests fast and deterministic?',
                ['testing', 'database'],
            ),
            (
                'How would you design background job processing (Celery/RQ/arq) for a {role} '
                'workload that must retry safely?',
                ['jobs', 'retries', 'queues'],
            ),
            (
                'Explain GIL implications for a CPU-bound {role} task and how you would parallelize it.',
                ['GIL', 'concurrency'],
            ),
            (
                'How would you migrate a Flask monolith toward FastAPI modules without downtime?',
                ['migration', 'FastAPI', 'architecture'],
            ),
            (
                'What caching layers would you add in front of a read-heavy {role} endpoint, '
                'and how do you invalidate them?',
                ['caching', 'Redis'],
            ),
            (
                'How would you secure secrets and DB credentials for a {role} service in Docker Compose '
                'and in Kubernetes?',
                ['secrets', 'security'],
            ),
        ],
        'senior': [
            (
                'Design a Python service boundary for a {role} platform that must support '
                'horizontal scaling and graceful degradation when Redis is down.',
                ['architecture', 'Redis', 'resilience'],
            ),
            (
                'How would you profile and fix a CPU hotspot in a production Python {role} worker '
                'processing large job batches?',
                ['profiling', 'performance'],
            ),
            (
                'What packaging, typing, and CI practices would you enforce for a multi-package '
                'Python monorepo used by {role} teams?',
                ['packaging', 'CI', 'typing'],
            ),
        ],
    },
    'frontend': {
        'junior': [
            (
                'Explain the difference between props and state in React, and how a {role} would '
                'decide where data should live.',
                ['React', 'props', 'state'],
            ),
            (
                'What causes a React component to re-render, and how can a {role} avoid unnecessary '
                'updates in a list view?',
                ['React', 'rendering'],
            ),
            (
                'How does the browser event loop relate to UI responsiveness for a {role} building '
                'interactive forms?',
                ['browser', 'event loop'],
            ),
        ],
        'mid': [
            (
                'How would you manage client-side routing and protected routes in a SPA for a '
                '{role} dashboard?',
                ['routing', 'auth'],
            ),
            (
                'Compare controlled vs uncontrolled form inputs in React. Which approach fits a '
                '{role} complex multi-step form and why?',
                ['forms', 'React'],
            ),
            (
                'How would you structure API error handling and loading states in a {role} UI so '
                'users always know what failed?',
                ['UX', 'API', 'errors'],
            ),
        ],
        'senior': [
            (
                'How would you design a frontend architecture for a {role} product that needs '
                'code-splitting, shared design tokens, and multiple teams contributing?',
                ['architecture', 'design system'],
            ),
            (
                'Describe a performance budget and measurement plan for a {role} critical path '
                '(LCP/INP) before a major release.',
                ['performance', 'Web Vitals'],
            ),
            (
                'What accessibility and internationalization constraints would you bake into a '
                '{role} component library from day one?',
                ['a11y', 'i18n'],
            ),
        ],
    },
    'data': {
        'junior': [
            (
                'What is the difference between supervised and unsupervised learning, and which '
                'would you use to group similar customer tickets?',
                ['ML', 'supervised', 'unsupervised'],
            ),
            (
                'Explain train/validation/test splits. How would you avoid leaking future '
                'information into training?',
                ['evaluation', 'leakage'],
            ),
            (
                'How would you clean missing values in a tabular dataset before a model '
                'training run?',
                ['data cleaning', 'missing values'],
            ),
            (
                'When training a classification model in Python, what is the difference between '
                'overfitting and underfitting, and what are two techniques to prevent overfitting?',
                ['overfitting', 'regularization', 'cross-validation'],
            ),
            (
                'What is the bias-variance tradeoff, and how does it show up when you pick a '
                'model that is too simple or too complex?',
                ['bias', 'variance', 'model selection'],
            ),
            (
                'How would you evaluate a binary classifier beyond raw accuracy? Name two metrics '
                'and when each is more useful.',
                ['metrics', 'precision', 'recall'],
            ),
            (
                'Explain what a confusion matrix shows and how you would use it after training '
                'a classifier.',
                ['evaluation', 'confusion matrix'],
            ),
            (
                'What is feature scaling (normalization/standardization), and when does it matter '
                'for algorithms like logistic regression or k-NN?',
                ['features', 'preprocessing'],
            ),
        ],
        'mid': [
            (
                'Compare precision and recall. Which metric would you prioritize for a rare '
                'fraud detection model and why?',
                ['metrics', 'precision', 'recall'],
            ),
            (
                'How would you design a feature store vs ad-hoc notebooks for a team '
                'shipping models to production?',
                ['features', 'MLOps'],
            ),
            (
                'Explain overfitting. What regularization or early-stopping approach would you '
                'apply in a gradient boosting pipeline?',
                ['overfitting', 'regularization'],
            ),
            (
                'How would you detect and handle class imbalance before training a classifier?',
                ['imbalance', 'sampling', 'metrics'],
            ),
            (
                'Walk through how you would choose between a linear model and a tree-based model '
                'for a tabular prediction problem.',
                ['model selection', 'tabular'],
            ),
            (
                'How would you version datasets and models so a {role} can reproduce last month’s '
                'production prediction exactly?',
                ['reproducibility', 'MLOps', 'versioning'],
            ),
            (
                'Describe how you would build an offline evaluation harness that catches label '
                'leakage before a model reaches staging.',
                ['evaluation', 'leakage', 'QA'],
            ),
            (
                'When would you choose embeddings + similarity search over a classical classifier '
                'for a text triage problem?',
                ['NLP', 'embeddings', 'retrieval'],
            ),
            (
                'How would you debug a sudden drop in online model performance after a silent '
                'upstream schema change?',
                ['debugging', 'data drift', 'monitoring'],
            ),
            (
                'Explain cross-validation for time-series data. Why is random k-fold often wrong?',
                ['time series', 'cross-validation'],
            ),
            (
                'How would you design a batch scoring pipeline for millions of rows with clear '
                'retry and idempotency guarantees?',
                ['batch', 'pipelines', 'reliability'],
            ),
            (
                'Compare feature importance methods (permutation, SHAP). How would you explain '
                'a risky prediction to a non-technical stakeholder?',
                ['explainability', 'SHAP'],
            ),
        ],
        'senior': [
            (
                'How would you productionize a model with monitoring for data drift, '
                'latency SLOs, and safe rollback?',
                ['MLOps', 'monitoring', 'drift'],
            ),
            (
                'Design an experimentation framework your org can use to A/B test model '
                'changes without contaminating offline metrics.',
                ['experimentation', 'A/B testing'],
            ),
            (
                'What governance and reproducibility practices would you require before a '
                'model can influence hiring or credit decisions?',
                ['governance', 'reproducibility'],
            ),
            (
                'How would you organize an ML platform team’s model registry, feature store, '
                'and CI so multiple {role} squads can ship independently?',
                ['platform', 'MLOps', 'architecture'],
            ),
            (
                'Describe a strategy for continuous training vs scheduled retraining when labels '
                'arrive with multi-day delay.',
                ['retraining', 'label delay'],
            ),
            (
                'How would you set up shadow deployment for a new ranking model and decide when '
                'to cut traffic over?',
                ['shadow deploy', 'ranking', 'rollout'],
            ),
            (
                'What tradeoffs would you make between model accuracy, inference cost, and '
                'p99 latency for a real-time {role} API?',
                ['latency', 'cost', 'tradeoffs'],
            ),
            (
                'How would you detect and mitigate training-serving skew in a large feature '
                'pipeline shared by several models?',
                ['training-serving skew', 'features'],
            ),
        ],
    },
    'devops': {
        'junior': [
            (
                'What is the difference between a Docker image and a container, and how would a '
                '{role} run a local API for testing?',
                ['Docker', 'containers'],
            ),
            (
                'Explain what a CI pipeline does. Name three checks a {role} should run before '
                'merging to main.',
                ['CI', 'testing'],
            ),
            (
                'What is infrastructure as code, and why would a {role} prefer it over clicking '
                'in a cloud console?',
                ['IaC', 'cloud'],
            ),
        ],
        'mid': [
            (
                'How would you design blue/green or canary deploys for a {role} service with '
                'minimal downtime?',
                ['deployment', 'canary'],
            ),
            (
                'Compare Kubernetes Deployments and StatefulSets. When does a {role} need each?',
                ['Kubernetes', 'workloads'],
            ),
            (
                'How would you set SLIs/SLOs and alerting for a {role} API so on-call is actionable?',
                ['SRE', 'alerting', 'SLO'],
            ),
        ],
        'senior': [
            (
                'Design a multi-environment promotion strategy (dev→staging→prod) for a {role} '
                'platform with secrets, migrations, and rollback.',
                ['environments', 'release'],
            ),
            (
                'How would you contain blast radius when a misconfigured Terraform change hits '
                'production for a {role} org?',
                ['Terraform', 'safety'],
            ),
            (
                'What observability architecture (logs/metrics/traces) would you standardize for '
                'dozens of microservices owned by {role} teams?',
                ['observability', 'architecture'],
            ),
        ],
    },
}

_DEFAULT_BANK: dict[str, list[tuple[str, list[str]]]] = {
    # Generic bank — use "you", never paste an unrelated job title into tech prompts.
    'junior': [
        (
            'Describe how HTTP request/response works end-to-end, and how you would debug a '
            '404 vs a 500 in an API.',
            ['HTTP', 'debugging'],
        ),
        (
            'What is the difference between SQL and NoSQL databases, and when would you '
            'choose PostgreSQL?',
            ['databases', 'SQL'],
        ),
        (
            'Explain version control branching (feature branch → PR → main) as used by a '
            'team day to day.',
            ['git', 'collaboration'],
        ),
        (
            'What is an API, and how would you design a simple REST endpoint that returns a list '
            'of resources with proper status codes?',
            ['API', 'REST'],
        ),
        (
            'Explain the difference between authentication and authorization with a short example.',
            ['security', 'auth'],
        ),
        (
            'What is a unit test, and why would you write one before changing existing code?',
            ['testing', 'unit tests'],
        ),
    ],
    'mid': [
        (
            'How would you design pagination and filtering for a high-traffic list API?',
            ['API design', 'pagination'],
        ),
        (
            'Compare caching strategies (in-memory vs Redis) for a read-heavy endpoint. '
            'What invalidation pitfalls matter?',
            ['caching', 'Redis'],
        ),
        (
            'How would you approach diagnosing intermittent production latency for a service?',
            ['latency', 'debugging'],
        ),
        (
            'How would you design idempotent write APIs so retries do not double-charge a user?',
            ['API design', 'idempotency'],
        ),
    ],
    'senior': [
        (
            'How would you break down a legacy monolith into services while keeping releases safe?',
            ['architecture', 'migration'],
        ),
        (
            'Describe a failure-mode analysis you would run before launching a new critical path.',
            ['reliability', 'failure modes'],
        ),
        (
            'What technical mentorship and code-review standards would you set for a team '
            'shipping weekly?',
            ['mentorship', 'code review'],
        ),
    ],
}

_ROLE_ALIASES: list[tuple[str, str]] = [
    ('java', 'java'),
    ('spring', 'java'),
    ('jvm', 'java'),
    ('kotlin', 'java'),
    ('python', 'python'),
    ('fastapi', 'python'),
    ('django', 'python'),
    ('flask', 'python'),
    ('backend', 'python'),
    ('frontend', 'frontend'),
    ('react', 'frontend'),
    ('typescript', 'frontend'),
    ('javascript', 'frontend'),
    ('ui ', 'frontend'),
    ('machine learning', 'data'),
    ('ml engineer', 'data'),
    ('ml engineering', 'data'),
    ('mle', 'data'),
    ('ml developer', 'data'),
    ('ml ', 'data'),
    (' ml', 'data'),
    ('data scientist', 'data'),
    ('data science', 'data'),
    ('data engineer', 'data'),
    ('data analyst', 'data'),
    ('ai engineer', 'data'),
    ('nlp', 'data'),
    ('deep learning', 'data'),
    ('devops', 'devops'),
    ('sre', 'devops'),
    ('platform engineer', 'devops'),
    ('kubernetes', 'devops'),
]


def normalize_difficulty(value: str | None) -> str:
    raw = (value or 'junior').strip().lower()
    if raw in {'middle', 'intermediate'}:
        return 'mid'
    if raw in DIFFICULTY_ORDER:
        return raw
    return 'junior'


def nudge_difficulty(requested: str | None, seniority: str | None) -> str:
    """Pull session difficulty toward CV seniority by at most one step."""
    base = normalize_difficulty(requested)
    if not seniority:
        return base
    senior = normalize_difficulty(seniority)
    bi = DIFFICULTY_ORDER.index(base)
    si = DIFFICULTY_ORDER.index(senior)
    if si > bi:
        return DIFFICULTY_ORDER[min(bi + 1, si)]
    if si < bi:
        return DIFFICULTY_ORDER[max(bi - 1, si)]
    return base


def _role_bank_key(target_role: str | None) -> str | None:
    blob = (target_role or '').lower()
    for needle, key in _ROLE_ALIASES:
        if needle in blob:
            return key
    return None


def _previous_questions(state: InterviewGraphState) -> list[str]:
    return [
        str(t.get('question') or '').strip()
        for t in (state.get('history') or [])
        if t.get('question')
    ]


def _variation_seed(state: InterviewGraphState, target_role: str | None) -> str:
    """Seed so consecutive turns diverge; include session id so reruns are not sticky."""
    hist = _previous_questions(state)
    sid = state.get('session_id') or ''
    material = f"{sid}|{target_role or ''}|{len(hist)}|{'||'.join(hist[-8:])}|{random.random()}"
    digest = hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]
    return f'{digest}-{random.randint(1000, 9999)}'


def _normalize_question(text: str) -> str:
    return re.sub(r'\s+', ' ', (text or '').strip().lower())


def _question_similarity(a: str, b: str) -> float:
    ta = {w for w in re.findall(r'[a-z0-9]+', _normalize_question(a)) if len(w) > 2}
    tb = {w for w in re.findall(r'[a-z0-9]+', _normalize_question(b)) if len(w) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _is_duplicate_question(question: str, previous: list[str], *, threshold: float = 0.68) -> bool:
    qn = _normalize_question(question)
    for prev in previous:
        pn = _normalize_question(prev)
        if not pn:
            continue
        if qn == pn or qn in pn or pn in qn:
            return True
        if _question_similarity(qn, pn) >= threshold:
            return True
    return False


def _pick_stub_question(
    *,
    target_role: str,
    difficulty: str,
    previous: list[str],
    seed: str,
) -> dict[str, Any]:
    bank_key = _role_bank_key(target_role)
    bank = _ROLE_QUESTION_BANKS.get(bank_key or '', _DEFAULT_BANK)
    level = normalize_difficulty(difficulty)

    def _format(template: str) -> str:
        if '{role}' in template:
            return template.format(role=target_role)
        return template

    # Prefer current level, then other levels in the SAME role bank.
    # Only fall back to the generic default bank after the role bank is exhausted.
    pools: list[tuple[str, list[str]]] = []
    seen_templates: set[str] = set()
    for lvl in (level, *(d for d in DIFFICULTY_ORDER if d != level)):
        for template, topics in list(bank.get(lvl) or []):
            if template not in seen_templates:
                pools.append((template, topics))
                seen_templates.add(template)

    unused = [
        (template, topics)
        for template, topics in pools
        if not _is_duplicate_question(_format(template), previous)
    ]

    if not unused and bank is not _DEFAULT_BANK:
        for lvl in DIFFICULTY_ORDER:
            for template, topics in list(_DEFAULT_BANK.get(lvl) or []):
                if template not in seen_templates:
                    pools.append((template, topics))
                    seen_templates.add(template)
        unused = [
            (template, topics)
            for template, topics in pools
            if not _is_duplicate_question(_format(template), previous)
        ]

    if unused:
        # Prefer diverse picks: rank candidates by seed hash (not just index 0)
        def _rank(item: tuple[str, list[str]]) -> int:
            return int(hashlib.md5(f'{seed}|{item[0][:80]}'.encode('utf-8')).hexdigest(), 16)

        template, topics = max(unused, key=_rank)
    else:
        # All exhausted — pick the least-recently used (avoid sticky repeats like HTTP)
        def _recency(item: tuple[str, list[str]]) -> int:
            q = _format(item[0])
            for i in range(len(previous) - 1, -1, -1):
                if _is_duplicate_question(q, [previous[i]]):
                    return i
            return -1

        ranked = sorted(pools, key=_recency)
        template, topics = ranked[0] if ranked else (
            'Explain a recent technical tradeoff you made and why.',
            ['tradeoffs'],
        )

    question = _format(template)
    return {
        'question': question,
        'topics': topics,
        'difficulty': level,
        'rationale': f'Stub technical question for {target_role} at {level} level.',
    }


def _parse_question_payload(raw: str) -> dict[str, Any]:
    payload = extract_json_payload(raw)
    data = repair_json(payload)
    if not isinstance(data, dict):
        raise ValidationError('Question LLM response was not a JSON object')
    question = str(data.get('question') or '').strip()
    if not question or len(question) < 12:
        raise ValidationError('Question LLM response missing a usable question')
    # Reject obvious soft-skill filler
    soft = re.compile(
        r'^\s*(tell me about yourself|what are your (strengths|weaknesses)|why (do you|should we))\b',
        re.I,
    )
    if soft.search(question):
        raise ValidationError('Generated question looks like soft-skill filler')
    topics = data.get('topics') or []
    if not isinstance(topics, list):
        topics = [str(topics)]
    return {
        'question': question,
        'topics': [str(t).strip() for t in topics if str(t).strip()][:8],
        'difficulty': normalize_difficulty(str(data.get('difficulty') or 'junior')),
        'rationale': str(data.get('rationale') or '').strip() or None,
    }


def load_cv_seniority(db: Session | None, cv_id: int | None) -> tuple[str | None, str]:
    """Return (seniority_level, short context string) from CV if available."""
    if not db or not cv_id:
        return None, 'No CV linked; using session difficulty only.'
    from app import models

    cv = db.query(models.CVProfile).filter(models.CVProfile.id == cv_id).first()
    if not cv:
        return None, f'CV id={cv_id} not found; using session difficulty only.'

    structured: dict[str, Any] = {}
    if cv.structured_data:
        try:
            structured = json.loads(cv.structured_data)
        except json.JSONDecodeError:
            structured = {}
    level = estimate_candidate_level(structured, cv.summary or '')
    skills = ', '.join(str(s) for s in (structured.get('skills') or [])[:12])
    ctx = (
        f'Estimated seniority={level}. '
        f'Summary: {(cv.summary or structured.get("summary") or "n/a")[:240]}. '
        f'Skills: {skills or "n/a"}.'
    )
    return level, ctx


def generate_question_payload(
    *,
    target_role: str,
    difficulty: str,
    previous_questions: list[str],
    seniority_context: str,
    variation_seed: str,
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """Generate one technical question (LLM or role-aware stub)."""
    role = (target_role or '').strip() or 'Software Engineer'
    level = normalize_difficulty(difficulty)
    client = llm or get_llm_client()
    provider = (settings.llm_provider or 'stub').strip().lower()

    if provider == 'stub' or isinstance(client, StubClient):
        return _pick_stub_question(
            target_role=role,
            difficulty=level,
            previous=previous_questions,
            seed=variation_seed,
        )

    prev_block = (
        '\n'.join(f'- {q}' for q in previous_questions)
        if previous_questions
        else '(none yet — choose a strong opener)'
    )
    prompt = render_prompt(
        'interview_question_prompt.txt',
        TARGET_ROLE=role,
        DIFFICULTY=level,
        SENIORITY_CONTEXT=seniority_context or 'n/a',
        PREVIOUS_QUESTIONS=prev_block,
        VARIATION_SEED=variation_seed,
    )

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            repair_hint = ''
            if attempt > 1:
                repair_hint = (
                    '\n\nPrevious output was invalid or repeated a past question. '
                    'Respond with ONLY a NEW JSON object for a different topic.'
                )
            raw = client.generate(prompt + repair_hint, max_tokens=1024, json_mode=True)
            parsed = _parse_question_payload(raw)
            if _is_duplicate_question(parsed['question'], previous_questions):
                raise ValidationError('Generated question duplicates a previous one')
            parsed['source'] = 'llm'
            return parsed
        except (ValidationError, ExternalServiceError) as exc:
            last_error = exc
            logger.warning('interview question attempt %s failed: %s', attempt, exc)

    logger.warning('Falling back to stub question bank after LLM failure: %s', last_error)
    stub = _pick_stub_question(
        target_role=role,
        difficulty=level,
        previous=previous_questions,
        seed=variation_seed,
    )
    stub['source'] = 'stub'
    stub['rationale'] = (
        f"{stub.get('rationale') or 'Stub question'} "
        f"(LLM unavailable: {type(last_error).__name__ if last_error else 'unknown'})"
    )
    return stub


def run_question_agent(
    state: InterviewGraphState,
    *,
    db: Session | None = None,
    llm: LLMClient | None = None,
) -> InterviewGraphState:
    """Generate next question, append to history, set current_question."""
    target_role = (state.get('target_role') or 'Software Engineer').strip()
    requested = state.get('difficulty')
    seniority, seniority_ctx = load_cv_seniority(db, state.get('cv_id'))
    difficulty = nudge_difficulty(requested, seniority)
    previous = _previous_questions(state)
    seed = _variation_seed(state, target_role)

    logger.info(
        'question_agent role=%r requested=%s nudged=%s seniority=%s prev=%s',
        target_role,
        requested,
        difficulty,
        seniority,
        len(previous),
    )

    payload = generate_question_payload(
        target_role=target_role,
        difficulty=difficulty,
        previous_questions=previous,
        seniority_context=seniority_ctx,
        variation_seed=seed,
        llm=llm,
    )

    asked_at = datetime.now(timezone.utc).isoformat()
    update = append_turn(
        {**state, 'difficulty': difficulty},
        question=payload['question'],
        difficulty=payload.get('difficulty') or difficulty,
        topics=payload.get('topics'),
        asked_at=asked_at,
    )
    update = append_interview_node_log(
        update,
        'question_agent',
        {
            'event': 'question_generated',
            'topics': payload.get('topics'),
            'difficulty': update.get('difficulty'),
            'rationale': payload.get('rationale'),
            'source': payload.get('source'),
            'variation_seed': seed,
        },
    )
    if update.get('status') in {None, 'pending'}:
        update['status'] = 'active'
    return update
