"""Interview Evaluate Agent (P7-03): score answers with structured feedback (§8.5)."""

from __future__ import annotations

import difflib
import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Literal

from app.clients.llm_client import LLMClient, StubClient, get_llm_client
from app.core.config import settings
from app.core.exceptions import ExternalServiceError, ValidationError
from app.interview.state import (
    InterviewGraphState,
    append_interview_node_log,
    apply_evaluation_to_pending_turn,
    find_pending_turn_index,
)
from app.services.cv_parser import extract_json_payload, repair_json
from app.services.prompt_loader import render_prompt

logger = logging.getLogger(__name__)

Relevance = Literal['on_topic', 'partial', 'off_topic']

_STOPWORDS = frozenset(
    {
        'a',
        'an',
        'the',
        'and',
        'or',
        'of',
        'to',
        'in',
        'on',
        'for',
        'with',
        'is',
        'are',
        'was',
        'were',
        'be',
        'been',
        'being',
        'that',
        'this',
        'these',
        'those',
        'it',
        'as',
        'at',
        'by',
        'from',
        'how',
        'what',
        'when',
        'where',
        'why',
        'which',
        'who',
        'whom',
        'your',
        'you',
        'would',
        'could',
        'should',
        'do',
        'does',
        'did',
        'into',
        'about',
        'over',
        'under',
        'than',
        'then',
        'them',
        'they',
        'their',
        'there',
        'here',
        'have',
        'has',
        'had',
        'will',
        'can',
        'may',
        'might',
        'must',
        'not',
        'no',
        'yes',
        'if',
        'else',
        'also',
        'just',
        'like',
        'use',
        'used',
        'using',
        'explain',
        'describe',
        'difference',
        'between',
        'one',
        'situation',
        'example',
        'please',
        'role',
        'task',
        'service',
        'developer',
        'engineer',
        'junior',
        'senior',
        'mid',
    }
)

# Soft-skill / unrelated deflection
_OFF_TOPIC_MARKERS = re.compile(
    r'\b('
    r'my hobby|my hobbies|favourite colour|favorite color|tell you about myself|'
    r'i love pizza|weather today|unrelated|not sure what you.?re asking|'
    r'i prefer cats|football team'
    r')\b',
    re.I,
)

# Candidate rejects or challenges the question premise (full-sentence meaning)
_PUSHBACK_MARKERS = re.compile(
    r'\b('
    r'shouldn.?t|wouldn.?t|doesn.?t make sense|isn.?t (my|a|the) (job|role|responsibility)|'
    r'not (my|the|a) (job|role|responsibility)|out of scope|wrong (role|question)|'
    r'inappropriate|doesn.?t (apply|belong)|mis(match|aligned)|'
    r'not something .{0,48}(would|should)|i (would|will) not|'
    r'never (would|should)|beyond (my|the) (role|scope)|'
    r'a .{0,40} shouldn.?t|an .{0,40} shouldn.?t'
    r')\b',
    re.I,
)

# Concept cues that signal a real technical answer (not mere echo of the prompt)
_CONCEPT_CUES = re.compile(
    r'\b('
    r'request|response|header|body|status|status code|404|500|client|server|'
    r'endpoint|api|http|https|tcp|latency|timeout|cache|redis|sql|nosql|'
    r'postgres|index|transaction|thread|async|await|exception|stack|trace|'
    r'arraylist|linkedlist|hashmap|equals|hashcode|docker|kubernetes|'
    r'branch|merge|pull request|ci|cd|deploy|observability|sla|slo|'
    r'precision|recall|overfitting|underfitting|regularization|cross.?validation|'
    r'feature|model|props|state|render|'
    r'pagination|invalidat|trade-?off|versus|compared|jsonb|mongodb|dynamodb|'
    r'supervised|unsupervised|confusion|bias|variance|classifier|validation'
    r')\b',
    re.I,
)

_DONT_KNOW = re.compile(
    r'^\s*('
    r'i\s*(do\s*n[o\'’]?t|dont)\s*know'
    r'|idk'
    r'|no\s*idea'
    r'|not\s*sure'
    r'|i\s*have\s*no\s*(idea|clue)'
    r'|pass'
    r'|skip'
    r'|dunno'
    r')\b.*$',
    re.I | re.S,
)

# Broad uncertainty / nerves / knowledge-gap *signals* — any wording that hits these,
# not a closed list of full canned sentences.
_UNCERTAINTY_SIGNALS = re.compile(
    r'\b('
    r'idk|dunno|blanking|'
    r'(don\'?t|do\s+not|dont)\s+(know|remember|understand|recall|get\s+it)|'
    r'(don\'?t|do\s+not|dont)\s+feel\s+(ready|confident|comfortable|prepared)|'
    r'(not|never|hardly)\s+(very\s+|really\s+|too\s+|entirely\s+|completely\s+|quite\s+)?'
    r'(sure|certain|confident|comfortable|familiar|clear|ready|prepared|secure)|'
    r'(no|zero)\s+(idea|clue)|'
    r'(unsure|uncertain|unfamiliar|unprepared|insecure|hesitant)|'
    r'(scared|afraid|nervous|anxious|worried|intimidated|panicking|panic)|'
    r'(uncomfortable|awkward)\s+(answering|to\s+answer|with\s+this)?|'
    r'(lack|lacking|low|weak|limited|poor)\s+(of\s+)?'
    r'(confidence|knowledge|experience|understanding)|'
    r'(drawing|draw)\s+a\s+blank|'
    r'(can\'?t|cannot|couldn\'?t)\s+(remember|recall|answer|explain|think)|'
    r'(pass|skip)\s*(on\s+)?(this|it)?|'
    r'(beyond|outside|out\s+of)\s+my\s+(knowledge|expertise|experience|depth)|'
    r'(need|would\s+need|have\s+to)\s+to\s+(look|read|study|review|google)\s+'
    r'(this|it|that)\s*up|'
    r'(forgot|forgotten)\s+(how|what|this)|'
    r'(struggling|struggle)\s+(with|to\s+answer)|'
    r'(brain\s+fart|mind\s+went\s+blank)|'
    r'(not\s+my\s+(strong|best)\s+(suit|area|topic))|'
    r'(wish\s+i\s+(knew|remembered))|'
    r'first\s+time\s+(hearing|seeing|learning)\s+(about\s+|of\s+)?(this|it)?'
    r')\b',
    re.I,
)

_SELF_KNOWLEDGE_STATE = re.compile(
    r'\b('
    r'my\s+(knowledge|understanding|experience|confidence)|'
    r'this\s+(topic|subject|question|one)|'
    r'(answering|answer)\s+(this|right\s+now)'
    r')\b',
    re.I,
)

_EDGE_CASE = re.compile(
    r'\b('
    r'edge\s*case|failure\s*mode|pitfall|caveat|gotcha|jsonb|'
    r'however|one\s+catch|watch\s*out|limitation'
    r')\b',
    re.I,
)

# Short coaching blurbs keyed by question topic (heuristic / offline path)
_TEACHING_HINTS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r'\b(precision|recall)\b', re.I),
        'Precision = of the predicted positives, how many were correct; recall = of the real '
        'positives, how many you caught. For rare fraud, prioritize recall (catch more fraud) '
        'even if you get more false alarms — missing fraud is usually costlier than extra reviews. '
        'Mention the precision–recall tradeoff and that accuracy alone is misleading on imbalanced data.',
    ),
    (
        re.compile(r'\b(overfit|underfit|regulariz|cross.?valid)\b', re.I),
        'Overfitting memorizes training noise (high train, low validation score); underfitting '
        'is too simple (poor on both). Prevent with cross-validation, regularization (L1/L2), '
        'early stopping, or simpler models — and always watch the train/validation gap.',
    ),
    (
        re.compile(r'\b(sql|nosql|postgres|mongodb)\b', re.I),
        'SQL databases use fixed schemas and strong relational queries; NoSQL favors flexible '
        'documents/keys and easier horizontal scale. A strong answer contrasts consistency vs '
        'flexibility and names when you would pick PostgreSQL vs MongoDB/DynamoDB.',
    ),
    (
        re.compile(r'\b(http|404|500|request.?response)\b', re.I),
        'HTTP is request → server handling → response with a status code. A 404 means the '
        'resource was not found (client/path issue); a 500 means the server failed while '
        'handling a valid-looking request — check logs and dependencies.',
    ),
    (
        re.compile(r'\b(git|branch|version control|pull request|pr)\b', re.I),
        'Day to day: create a feature branch from main, commit locally, open a pull request '
        'for review, address feedback, then merge back to main. Mention why branches isolate '
        'work and why PRs catch bugs before release.',
    ),
    (
        re.compile(r'\b(arraylist|linkedlist)\b', re.I),
        'ArrayList is array-backed (fast random access); LinkedList is node-based (cheaper '
        'mid-list inserts/removes, slower indexing). Say which fits read-heavy vs mutate-heavy use.',
    ),
    (
        re.compile(r'\b(supervised|unsupervised|train.?valid|bias.?variance)\b', re.I),
        'Tie your answer to the learning setup: labeled vs unlabeled data, how you split data, '
        'which metric matches the business cost of mistakes, and one concrete prevention step.',
    ),
    (
        re.compile(r'\b(re.?render|memo|usememo|usecallback|props|state|list view|virtualiz|shouldcomponentupdate)\b', re.I),
        'React re-renders when props, state, or context change, or when a parent re-renders. '
        'In lists, avoid re-creating props and callbacks each render: use stable keys, React.memo, '
        'useMemo/useCallback, and windowing (e.g. react-window) for very long lists.',
    ),
    (
        re.compile(r'\b(code.?split|lazy|suspense|design tokens|design system|monorepo|architecture|teams?)\b', re.I),
        'Split by route with React.lazy + Suspense; share design tokens and UI primitives in a '
        'versioned package; give each team clear ownership (CODEOWNERS) and enforce contract tests '
        'at package boundaries.',
    ),
    (
        re.compile(r'\b(api|error handling|error states?|loading states?|error boundary|retry)\b', re.I),
        'Centralize API calls in one typed client; model every request as idle/loading/success/error; '
        'show inline errors with a retry action, and catch unexpected failures in an error boundary '
        'plus a global toast so users always know what failed and can recover.',
    ),
    (
        re.compile(r'\b(performance|lcp|inp|web vitals|core web vitals|budget|critical path|cls)\b', re.I),
        'Define budgets for LCP, INP and CLS per page type, measure them in CI (Lighthouse lab) and in '
        'production (RUM), and block the release when a metric regresses past budget; then optimize '
        'the largest contentful element and long main-thread tasks.',
    ),
]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_+#.-]{1,}", (text or '').lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _question_snippet(question: str, max_len: int = 80) -> str:
    q = ' '.join((question or '').split())
    if len(q) <= max_len:
        return q
    return q[: max_len - 1].rstrip() + '…'


def _content_overlap(question: str, answer: str, target_role: str | None) -> set[str]:
    """Overlap that ignores role-title echo (those are not evidence of understanding)."""
    q_tokens = _tokens(question)
    a_tokens = _tokens(answer)
    role_tokens = _tokens(target_role or '')
    return (q_tokens & a_tokens) - role_tokens


def _teaching_hint(question: str) -> str:
    for pattern, hint in _TEACHING_HINTS:
        if pattern.search(question or ''):
            return hint
    return (
        'Restate the core idea the question asks about in 2–3 sentences, then add one short '
        'concrete example from real work or a project.'
    )


_UNCERTAINTY_KEYWORDS = frozenset(
    {
        'comfortable',
        'confident',
        'sure',
        'certain',
        'familiar',
        'nervous',
        'scared',
        'afraid',
        'anxious',
        'worried',
        'ready',
        'prepared',
        'remember',
        'recall',
        'understand',
        'knowledge',
        'expertise',
        'experienced',
    }
)


def _fuzzy_uncertainty_word(text: str) -> bool:
    """Detect uncertainty keywords even with small typos (e.g. "comfortab;e")."""
    for word in re.findall(r'[a-z]{4,}', text):
        if word in _UNCERTAINTY_KEYWORDS:
            return True
        for kw in _UNCERTAINTY_KEYWORDS:
            if abs(len(word) - len(kw)) <= 1 and difflib.SequenceMatcher(None, word, kw).ratio() >= 0.85:
                return True
    return False


def _is_uncertainty_reply(answer: str) -> bool:
    """
    Detect answers that mainly express a knowledge/confidence gap — any wording —
    rather than matching a fixed list of sentences.
    """
    a = (answer or '').strip()
    if not a:
        return False
    words = len(a.split())
    concept_hits = len(_CONCEPT_CUES.findall(a))

    # A real technical attempt with a hedge still counts as an answer, not pure uncertainty
    if concept_hits >= 2 and words >= 20:
        return False

    if _DONT_KNOW.match(a):
        return True

    signal_hits = len(_UNCERTAINTY_SIGNALS.findall(a))
    self_state = bool(_SELF_KNOWLEDGE_STATE.search(a))

    # Primary: uncertainty signals + little/no technical substance
    if signal_hits >= 1 and concept_hits == 0 and words <= 40:
        return True

    # Secondary: talking about own knowledge/topic without teaching anything technical
    if (
        self_state
        and concept_hits == 0
        and words <= 35
        and re.search(r'\b(not|no|weak|limited|poor|gap|lack|lacking|low)\b', a, re.I)
    ):
        return True

    # Typo-tolerant fallback: short negative answers with a fuzzy uncertainty keyword
    # (e.g. "i am not comfortab;e" → "not comfortable")
    if signal_hits == 0 and words <= 12:
        cleaned = re.sub(r'[^a-z\s]', '', a.lower())
        if re.search(r'\b(not|no|cant|cannot|never|dont)\b', cleaned) and _fuzzy_uncertainty_word(
            cleaned
        ):
            return True

    return False


def _cite_from_answer(answer: str, *, limit: int = 2) -> list[str]:
    """Pull short, concrete phrases from the answer so feedback is not generic."""
    text = ' '.join((answer or '').split())
    if not text:
        return []
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 24]
    cites: list[str] = []
    for sent in sentences:
        snippet = sent if len(sent) <= 110 else sent[:107].rstrip() + '…'
        cites.append(snippet)
        if len(cites) >= limit:
            break
    if not cites and len(text) > 20:
        cites.append(text[:110].rstrip() + ('…' if len(text) > 110 else ''))
    return cites


# Rotating openers per phrasing category so repeated "I don't know" replies
# never sound identical.
_NERVOUS_OPENERS = [
    'feeling nervous is completely normal — admitting it instead of bluffing is honest '
    'and shows real self-awareness.',
    'nerves are a sign you care — saying so honestly beats any bluff, and interviewers '
    'notice that maturity.',
    'everyone gets nervous; being upfront about it is honest and makes you come across '
    'as self-aware, which interviewers love.',
]

_COMFORT_OPENERS = [
    'saying you are not comfortable with this yet is honest — naming it beats guessing '
    'wildly, and that instinct already works in your favor.',
    'it is completely okay to not feel comfortable with a topic — being upfront is honest '
    'and keeps the interviewer on your side.',
    'drawing a line and saying you are not comfortable is honest and professional — far '
    'better than a shaky bluff.',
]

_CONFIDENCE_OPENERS = [
    'acknowledging a confidence gap takes real honesty — interviewers respect that far '
    'more than a vague bluff.',
    'being honest about your confidence level reads as maturity — it beats bluffing '
    'every single time.',
    'naming a confidence gap is a strength, not a weakness — honest candidates are the '
    'ones interviewers trust.',
]

_NOT_SURE_OPENERS = [
    'admitting you are not sure is honest — interviewers prefer that over a confident '
    'wrong guess, and this is the safest way to keep their trust.',
    '“not sure yet” is a perfectly strong answer — it is honest, and honesty keeps the '
    'interviewer trusting you.',
    'saying you are not sure beats guessing — honesty here actually builds credibility.',
    'being unsure is a normal part of learning; saying so honestly is exactly the right move.',
]

_DEFAULT_OPENERS = [
    'thanks for being honest about the gap — interviewers still want to see how you '
    'reason when stuck.',
    'being upfront about a gap is honest and human — now we can turn it into a quick win.',
    'you handled that honestly, and that counts — the next step is showing how you would '
    'tackle it.',
]


def _uncertainty_opener(answer: str) -> str:
    low = re.sub(r'[^a-z\s]', '', (answer or '').lower())
    if re.search(r'scared|afraid|nervous|anxious|worried|intimidated|panic', low):
        return random.choice(_NERVOUS_OPENERS)
    if re.search(r'uncomfortable|awkward|not\s+(feel(ing)?\s+)?(secure|safe|ready|comfortable)', low):
        return random.choice(_COMFORT_OPENERS)
    if re.search(r'confident|confidence|knowledge|unfamiliar|experience|expertise|depth', low):
        return random.choice(_CONFIDENCE_OPENERS)
    if re.search(
        r'not\s+(really\s+)?sure|unsure|uncertain|no\s+(idea|clue)|dont\s+know|idk',
        low,
    ):
        return random.choice(_NOT_SURE_OPENERS)
    return random.choice(_DEFAULT_OPENERS)


# Rotating coaching suggestions so repeated uncertainty answers never feel canned.
_UNCERTAINTY_TIPS = [
    "Next time, try the 'what I remember → what I'd look up → one small guess' structure — "
    'even a partial attempt scores.',
    'A tiny attempt still wins points: name one related concept you do know and connect it '
    'back to the question.',
    'When stuck, say what you would do to find the answer and add one hypothesis — that shows '
    'engineering instincts.',
    'Practise the definition → one example → one caveat pattern aloud; it turns blanks into answers.',
    'Give yourself ten seconds to outline a single-sentence answer — structure beats silence '
    'in every interview.',
    'Answer with the closest thing you are sure about — interviewers care how you reason, '
    'not just what you recall.',
]

_UNCERTAINTY_CLOSERS = [
    "You'll get there — every question you meet here is one fewer surprise on interview day.",
    'This is exactly what practice is for: better to face it here first than in the real room.',
    'Keep going — recognizing the gap is the first step to closing it, and you just took it.',
    'You are doing the right thing by training here; consistency turns gaps into strengths.',
    'Every senior engineer has blanked on a question before — bouncing back is the skill '
    'interviewers notice most.',
    'Read the model answer once, then next time try rewriting it in your own words — it sticks.',
]

_UNCERTAINTY_IMPROVEMENTS = [
    'Retry aloud using the model answer above in your own words.',
    'Use the remember → look up → guess structure next time you are unsure.',
    'Say one related concept you are sure about before admitting the gap.',
    'Turn the blank into a hypothesis: “I would start by checking…”.',
]


def evaluate_answer_heuristic(
    *,
    question: str,
    answer: str,
    difficulty: str = 'junior',
    target_role: str | None = None,
) -> dict[str, Any]:
    """
    Deterministic offline evaluator — judges answer *meaning*, not keyword echo.
    Used when LLM_PROVIDER=stub or as fallback. Feedback should coach, not only grade.
    """
    q = (question or '').strip()
    a = (answer or '').strip()
    snippet = _question_snippet(q)
    role = (target_role or '').strip()
    hint = _teaching_hint(q)

    if not a:
        feedback = (
            f'Regarding “{snippet}”: no answer was provided — that is okay; interviews reward '
            f'attempting a structure. Try definition → why it matters → one example. '
            f'Model answer to study: {hint}'
        )
        return {
            'score': 0.0,
            'feedback': feedback,
            'strengths': [],
            'improvements': ['Attempt a short structured answer even if you are unsure.'],
            'relevance': 'off_topic',
            'latency_ms': 0.0,
        }

    # Honest uncertainty / nerves — teach + motivate (never "drifts away")
    if _is_uncertainty_reply(a):
        opener = _uncertainty_opener(a)
        tip = random.choice(_UNCERTAINTY_TIPS)
        closer = random.choice(_UNCERTAINTY_CLOSERS)
        improvements = random.sample(_UNCERTAINTY_IMPROVEMENTS, 2)
        feedback = (
            f'Regarding “{snippet}”: {opener} '
            f'{tip} {closer} '
            f'Here is a short model answer to study for this question: {hint}'
        )
        return {
            'score': 1.0,
            'feedback': feedback,
            'strengths': ['Honest about a knowledge or confidence gap'],
            'improvements': improvements,
            'relevance': 'partial',
            'latency_ms': 0.0,
        }

    q_tokens = _tokens(q)
    meaningful = _content_overlap(q, a, role)
    overlap_ratio = (len(meaningful) / len(q_tokens)) if q_tokens else 0.0
    words = len(a.split())
    off_topic_hit = bool(_OFF_TOPIC_MARKERS.search(a))
    pushback = bool(_PUSHBACK_MARKERS.search(a))
    concept_hits = len(_CONCEPT_CUES.findall(a))
    has_example = bool(
        re.search(r'\b(for example|e\.g\.|such as|for instance|when i|in practice)\b', a, re.I)
    )
    has_tradeoff = bool(
        re.search(r'\b(trade-?off|versus|vs\.?|compared to|however|on the other hand)\b', a, re.I)
    )
    has_edge = bool(_EDGE_CASE.search(a))
    cites = _cite_from_answer(a)

    # Explicit unrelated chatter (pizza, hobbies) — not uncertainty
    if off_topic_hit or (
        q_tokens and overlap_ratio < 0.05 and concept_hits == 0 and words < 40 and not pushback
    ):
        score = 1.0 if words > 5 else 0.5
        feedback = (
            f'Regarding “{snippet}”: this reply does not engage the technical ask. '
            f'Reset and answer the question directly. Model answer to study: {hint}'
        )
        return {
            'score': score,
            'feedback': feedback,
            'strengths': [],
            'improvements': [
                'Stay on the technical topic of the question.',
                'Use the model answer to rebuild a short reply.',
            ],
            'relevance': 'off_topic',
            'latency_ms': 0.0,
        }

    # Candidate challenges a mismatched / ill-posed question (sentence-level meaning)
    if pushback and concept_hits == 0 and words < 40:
        score = 2.5 if words >= 6 else 1.5
        feedback = (
            f'Regarding “{snippet}”: you challenged the premise — fair when the ask is a poor fit '
            f'for the role. Add *why* it mismatches, then still show adjacent knowledge. '
            f'If you want a technical baseline for this prompt anyway: {hint}'
        )
        return {
            'score': score,
            'feedback': feedback,
            'strengths': ['Recognized a possible role/question mismatch'],
            'improvements': [
                'Add a short rationale for the pushback.',
                'Still demonstrate relevant knowledge or a domain-fit alternative.',
            ],
            'relevance': 'partial',
            'latency_ms': 0.0,
        }

    # Thin / vague: little conceptual substance even if some words overlap
    if words < 18 or (concept_hits == 0 and overlap_ratio < 0.15 and words < 45):
        score = 3.0 + min(1.5, concept_hits * 0.4 + len(meaningful) * 0.15)
        if pushback:
            score = min(score, 3.5)
        cite_bit = f' You started with “{cites[0]}” — expand that thought.' if cites else ''
        feedback = (
            f'Regarding “{snippet}”: partial credit — the reply is too thin to show mastery.{cite_bit} '
            f'Stretch into full sentences: define the idea, contrast options if asked, add one example. '
            f'Target content: {hint}'
        )
        return {
            'score': round(min(score, 5.0), 1),
            'feedback': feedback,
            'strengths': ['Attempted an answer'],
            'improvements': [
                'Expand into a coherent explanation.',
                'Include a brief example tied to the question.',
            ],
            'relevance': 'partial',
            'latency_ms': 0.0,
        }

    # Stronger answers: reward conceptual coverage + structure, not role-title echo
    base = 6.0 + min(2.0, concept_hits * 0.35) + min(1.2, overlap_ratio * 2.5)
    if has_example:
        base += 0.7
    if has_tradeoff:
        base += 0.5
    if has_edge:
        base += 0.6
    if words > 80:
        base += 0.3
    if pushback and concept_hits >= 2:
        base += 0.4
    if difficulty == 'senior' and not (has_example or has_tradeoff):
        base -= 0.8
    score = round(min(10.0, max(6.0, base)), 1)

    # Answer-specific praise (avoid identical boilerplate for every strong reply)
    parts = [f'Regarding “{snippet}”:']
    if score >= 9.0:
        parts.append('excellent answer.')
    elif score >= 7.5:
        parts.append('solid, interview-ready answer.')
    else:
        parts.append('good foundation with room to deepen.')

    if cites:
        parts.append(f'Strong point: “{cites[0]}”')
        if len(cites) > 1 and score >= 8.5:
            parts.append(f'Also effective: “{cites[1]}”')

    covered = []
    if has_example:
        covered.append('a concrete example')
    if has_tradeoff:
        covered.append('a clear contrast/tradeoff')
    if has_edge:
        covered.append('an edge case/limitation')
    if covered:
        parts.append('You included ' + ', '.join(covered) + '.')

    improvements: list[str] = []
    if score >= 9.0:
        parts.append('No major gaps for this question — reuse this structure on later turns.')
    elif has_edge or (has_example and has_tradeoff):
        parts.append(
            'Minor polish: name one operational risk (latency, consistency, or rollback) if asked again.'
        )
        improvements.append('Optionally mention an operational risk if relevant.')
    else:
        parts.append('Next time, add one edge case or failure mode tied specifically to this ask.')
        improvements.append('Mention an edge case or operational pitfall tied to the question.')

    return {
        'score': score,
        'feedback': ' '.join(parts).strip(),
        'strengths': [
            s
            for s in [
                'Clear explanation of the asked concepts' if concept_hits >= 2 else '',
                'Used an example' if has_example else '',
                'Discussed tradeoffs' if has_tradeoff else '',
                'Called out an edge case / limitation' if has_edge else '',
            ]
            if s
        ][:5]
        or ['Addressed the question with substantive detail'],
        'improvements': improvements,
        'relevance': 'on_topic',
        'latency_ms': 0.0,
    }


def _parse_eval_payload(raw: str, *, question: str) -> dict[str, Any]:
    payload = extract_json_payload(raw)
    data = repair_json(payload)
    if not isinstance(data, dict):
        raise ValidationError('Eval LLM response was not a JSON object')

    try:
        score = float(data.get('score'))
    except (TypeError, ValueError) as exc:
        raise ValidationError('Eval LLM response missing numeric score') from exc
    score = max(0.0, min(10.0, score))

    feedback = str(data.get('feedback') or '').strip()
    if not feedback:
        raise ValidationError('Eval LLM response missing feedback')

    # Truncated Gemini JSON often leaves dangling quotes / half sentences
    if (
        feedback.count("'") % 2 == 1
        or feedback.count('"') % 2 == 1
        or re.search(r"(you mentioned ['\"]|regarding .+:)\s*$", feedback, re.I)
        or (len(feedback) < 48 and not feedback.endswith(('.', '!', '?')))
    ):
        raise ValidationError('Eval LLM feedback looks truncated')

    # Ensure feedback references the question (acceptance criterion)
    snippet = _question_snippet(question, 48)
    q_tokens = _tokens(question)
    feedback_l = feedback.lower()
    references = (
        snippet[:20].lower() in feedback_l
        or any(t in feedback_l for t in list(q_tokens)[:6])
        or 'question' in feedback_l
        or 'asked' in feedback_l
        or 'regarding' in feedback_l
    )
    if not references:
        feedback = f'Regarding “{snippet}”: {feedback}'

    strengths = data.get('strengths') or []
    improvements = data.get('improvements') or []
    if not isinstance(strengths, list):
        strengths = [str(strengths)]
    if not isinstance(improvements, list):
        improvements = [str(improvements)]

    relevance = str(data.get('relevance') or 'partial').strip().lower()
    if relevance not in {'on_topic', 'partial', 'off_topic'}:
        relevance = 'partial'

    # Guardrail: never ask to "score higher" after an excellent mark
    if score >= 9.0:
        bad = re.compile(
            r'\b(to score higher|call out one edge case|add (an )?edge case to)\b',
            re.I,
        )
        if bad.search(feedback):
            feedback = bad.sub('', feedback).strip()
            feedback = re.sub(r'\s{2,}', ' ', feedback)
            if not feedback.endswith('.'):
                feedback += '.'
            feedback += ' Excellent depth for this question — keep this structure on later turns.'
        improvements = [
            i
            for i in improvements
            if not re.search(r'edge case|score higher|failure mode', i, re.I)
        ]

    return {
        'score': round(score, 1),
        'feedback': feedback,
        'strengths': [str(s).strip() for s in strengths if str(s).strip()][:6],
        'improvements': [str(s).strip() for s in improvements if str(s).strip()][:6],
        'relevance': relevance,
    }


def evaluate_answer(
    *,
    question: str,
    answer: str,
    target_role: str | None = None,
    difficulty: str | None = 'junior',
    llm: LLMClient | None = None,
) -> dict[str, Any]:
    """Score an answer; returns score, feedback, strengths, improvements, latency_ms."""
    started = time.perf_counter()
    client = llm or get_llm_client()
    provider = (settings.llm_provider or 'stub').strip().lower()
    role = (target_role or 'Software Engineer').strip()
    level = (difficulty or 'junior').strip().lower()

    if provider == 'stub' or isinstance(client, StubClient):
        result = evaluate_answer_heuristic(
            question=question,
            answer=answer,
            difficulty=level,
            target_role=role,
        )
        result['latency_ms'] = round((time.perf_counter() - started) * 1000, 2)
        return result

    # Pure uncertainty / nerves: keep the encouraging coach path — do not let the LLM
    # turn "I don't know" into a dry lecture that only quotes the phrase.
    if _is_uncertainty_reply(answer):
        result = evaluate_answer_heuristic(
            question=question,
            answer=answer,
            difficulty=level,
            target_role=role,
        )
        result['latency_ms'] = round((time.perf_counter() - started) * 1000, 2)
        result['source'] = 'uncertainty_coach'
        return result

    prompt = render_prompt(
        'interview_eval_prompt.txt',
        TARGET_ROLE=role,
        DIFFICULTY=level,
        QUESTION=question or '',
        ANSWER=answer or '',
    )

    last_error: Exception | None = None
    for attempt in range(1, 3):
        try:
            repair_hint = ''
            if attempt > 1:
                repair_hint = (
                    '\n\nPrevious output was invalid. Respond with ONLY the JSON object.'
                )
            # Keep output short for live conversational latency
            raw = client.generate(prompt + repair_hint, max_tokens=1024, json_mode=True)
            parsed = _parse_eval_payload(raw, question=question)
            parsed['latency_ms'] = round((time.perf_counter() - started) * 1000, 2)
            return parsed
        except (ValidationError, ExternalServiceError) as exc:
            last_error = exc
            logger.warning('interview eval attempt %s failed: %s', attempt, exc)

    logger.warning('Falling back to heuristic eval after LLM failure: %s', last_error)
    result = evaluate_answer_heuristic(
        question=question,
        answer=answer,
        difficulty=level,
        target_role=role,
    )
    result['latency_ms'] = round((time.perf_counter() - started) * 1000, 2)
    return result


def run_evaluate_agent(
    state: InterviewGraphState,
    *,
    answer: str,
    llm: LLMClient | None = None,
) -> InterviewGraphState:
    """Evaluate the pending turn's answer and update history / running score."""
    history = list(state.get('history') or [])
    idx = find_pending_turn_index(history)
    if idx is None:
        warnings = list(state.get('warnings') or [])
        warnings.append('evaluate_agent: no pending question to score')
        update = {**state, 'warnings': warnings}
        return append_interview_node_log(update, 'evaluate_agent', {'event': 'skipped_no_pending'})

    turn = history[idx]
    question = str(turn.get('question') or state.get('current_question') or '')
    result = evaluate_answer(
        question=question,
        answer=answer,
        target_role=state.get('target_role'),
        difficulty=turn.get('difficulty') or state.get('difficulty'),
        llm=llm,
    )

    answered_at = datetime.now(timezone.utc).isoformat()
    update = apply_evaluation_to_pending_turn(
        state,
        answer=answer,
        score=float(result['score']),
        feedback=str(result['feedback']),
        answered_at=answered_at,
    )
    return append_interview_node_log(
        update,
        'evaluate_agent',
        {
            'event': 'answer_evaluated',
            'score': result['score'],
            'relevance': result.get('relevance'),
            'latency_ms': result.get('latency_ms'),
            'strengths': result.get('strengths'),
            'improvements': result.get('improvements'),
        },
    )
