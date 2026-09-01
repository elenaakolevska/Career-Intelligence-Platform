"""Lightweight heuristic CV extraction used when LLM provider is stub/offline."""

from __future__ import annotations

import re

from app.schemas.cv import EducationEntry, ExperienceEntry, StructuredCV


_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
_PHONE_RE = re.compile(r'(\+?\d[\d\s().-]{7,}\d)')
_SKILL_SPLIT_RE = re.compile(r'[,;/|•·\n]+')


def _section_body(text: str, headings: list[str]) -> str:
    lowered = text.lower()
    for heading in headings:
        pattern = re.compile(
            rf'(?:^|\n)\s*{re.escape(heading)}\s*:?\s*\n(.*?)(?=\n\s*(?:experience|education|skills|projects|certifications|summary|languages)\b|\Z)',
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        idx = lowered.find(heading.lower())
        if idx >= 0:
            return text[idx + len(heading) : idx + len(heading) + 400].strip()
    return ''


def heuristic_parse_cv(raw_text: str) -> StructuredCV:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    name = lines[0] if lines else None
    email_match = _EMAIL_RE.search(raw_text)
    phone_match = _PHONE_RE.search(raw_text)

    skills_body = _section_body(raw_text, ['skills', 'technical skills', 'competencies'])
    skills = [s.strip() for s in _SKILL_SPLIT_RE.split(skills_body) if s.strip()][:30]

    experience: list[ExperienceEntry] = []
    exp_body = _section_body(raw_text, ['experience', 'work experience', 'employment'])
    for block in re.split(r'\n{2,}', exp_body):
        block_lines = [b.strip() for b in block.splitlines() if b.strip()]
        if not block_lines:
            continue
        title = block_lines[0]
        company = block_lines[1] if len(block_lines) > 1 else None
        experience.append(
            ExperienceEntry(
                title=title,
                company=company,
                description=' '.join(block_lines[2:]) if len(block_lines) > 2 else None,
            )
        )

    education: list[EducationEntry] = []
    edu_body = _section_body(raw_text, ['education', 'academic'])
    for block in re.split(r'\n{2,}', edu_body):
        block_lines = [b.strip() for b in block.splitlines() if b.strip()]
        if not block_lines:
            continue
        education.append(
            EducationEntry(
                degree=block_lines[0],
                institution=block_lines[1] if len(block_lines) > 1 else None,
                details=' '.join(block_lines[2:]) if len(block_lines) > 2 else None,
            )
        )

    summary_body = _section_body(raw_text, ['summary', 'profile', 'about'])
    certs_body = _section_body(raw_text, ['certifications', 'certificates'])
    certifications = [c.strip() for c in _SKILL_SPLIT_RE.split(certs_body) if c.strip()][:20]

    return StructuredCV(
        name=name,
        email=email_match.group(0) if email_match else None,
        phone=phone_match.group(0) if phone_match else None,
        summary=summary_body or None,
        skills=skills,
        experience=experience[:10],
        education=education[:10],
        certifications=certifications,
        languages=[],
        location=None,
    )
