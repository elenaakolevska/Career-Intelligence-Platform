"""ATS optimization scoring against extracted CV text/structure."""

from __future__ import annotations

import re
from typing import Iterable

from app.schemas.cv import ATSIssue, ATSResult, StructuredCV


def _has_email(text: str) -> bool:
    return bool(re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', text))


def _has_phone(text: str) -> bool:
    return bool(re.search(r'(\+?\d[\d\s().-]{7,}\d)', text))


def _section_present(text: str, headings: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(re.search(rf'(?m)^\s*{re.escape(h.lower())}\s*:?\s*$', lowered) or
               re.search(rf'\b{re.escape(h.lower())}\b', lowered) for h in headings)


def _has_metrics(text: str) -> bool:
    return bool(
        re.search(
            r'(\d+\s*%|\b\d{1,3}(?:,\d{3})+\b|\b\d+\+?\s*(users|customers|requests|ms|s|tb|gb|mb)\b)',
            text,
            re.I,
        )
    )


def _experience_has_dates(structured: StructuredCV | None, text: str) -> bool:
    if structured and structured.experience:
        dated = sum(
            1
            for exp in structured.experience
            if (exp.start_date or exp.end_date or '')
            and str(exp.start_date or exp.end_date).strip()
        )
        if dated >= max(1, len(structured.experience) // 2):
            return True
    # Year ranges or month-year patterns in text
    return bool(re.search(r'\b(19|20)\d{2}\b.*\b(19|20)\d{2}|present|current\b', text, re.I))


def score_ats(
    raw_text: str | None,
    structured: StructuredCV | None = None,
    *,
    filename: str | None = None,
) -> ATSResult:
    """
    Score common ATS-breaking issues (formatting/structure, not just keywords).

    Structured extraction can support scoring but does not auto-pass sections —
    clear text evidence is still required for a high score.
    """
    text = (raw_text or '').strip()
    issues: list[ATSIssue] = []
    deductions = 0

    email_in_text = _has_email(text)
    email_structured = bool(structured and structured.email)
    if not email_in_text and not email_structured:
        issues.append(ATSIssue(code='contact_email', severity='high', message='No email address detected'))
        deductions += 18
    elif not email_in_text and email_structured:
        issues.append(
            ATSIssue(
                code='contact_email_text',
                severity='medium',
                message='Email found in parse but not clearly visible in CV text (ATS risk)',
            )
        )
        deductions += 6

    phone_in_text = _has_phone(text)
    phone_structured = bool(structured and structured.phone)
    if not phone_in_text and not phone_structured:
        issues.append(ATSIssue(code='contact_phone', severity='medium', message='No phone number detected'))
        deductions += 8
    elif not phone_in_text and phone_structured:
        issues.append(
            ATSIssue(
                code='contact_phone_text',
                severity='low',
                message='Phone found in parse but not clearly visible in CV text',
            )
        )
        deductions += 3

    skills_heading = _section_present(text, ['skills', 'technical skills', 'competencies', 'tech stack'])
    skills_count = len(structured.skills) if structured and structured.skills else 0
    if not skills_heading and skills_count == 0:
        issues.append(ATSIssue(code='skills_section', severity='high', message='No clear skills section'))
        deductions += 18
    elif not skills_heading:
        issues.append(
            ATSIssue(
                code='skills_heading',
                severity='medium',
                message='Skills appear present but no clear Skills heading for ATS parsers',
            )
        )
        deductions += 8
    elif skills_count and skills_count < 3:
        issues.append(
            ATSIssue(
                code='skills_sparse',
                severity='medium',
                message='Very few skills listed; ATS keyword matching may under-rank this CV',
            )
        )
        deductions += 6

    experience_heading = _section_present(
        text, ['experience', 'work experience', 'employment', 'professional experience', 'work history']
    )
    experience_count = len(structured.experience) if structured and structured.experience else 0
    if not experience_heading and experience_count == 0:
        issues.append(ATSIssue(code='experience_section', severity='high', message='No clear experience section'))
        deductions += 18
    elif not experience_heading:
        issues.append(
            ATSIssue(
                code='experience_heading',
                severity='medium',
                message='Experience content found but no clear Experience heading',
            )
        )
        deductions += 8

    education_heading = _section_present(text, ['education', 'academic', 'qualifications'])
    education_count = len(structured.education) if structured and structured.education else 0
    if not education_heading and education_count == 0:
        issues.append(ATSIssue(code='education_section', severity='medium', message='No clear education section'))
        deductions += 10
    elif not education_heading:
        issues.append(
            ATSIssue(
                code='education_heading',
                severity='low',
                message='Education content found but no clear Education heading',
            )
        )
        deductions += 4

    if not _section_present(text, ['summary', 'profile', 'objective', 'about']):
        if not (structured and structured.summary):
            issues.append(
                ATSIssue(
                    code='summary_section',
                    severity='low',
                    message='No summary/profile section; many ATS roles expect a short professional summary',
                )
            )
            deductions += 4

    if structured and not structured.name and not re.search(r'(?m)^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3}\s*$', text[:400]):
        issues.append(ATSIssue(code='missing_name', severity='high', message='Candidate name not clearly detected'))
        deductions += 10

    location_ok = bool(structured and structured.location) or bool(
        re.search(r'\b(remote|[A-Z][a-z]+(?:,\s*[A-Z]{2})?)\b', text[:500])
    )
    if not location_ok:
        issues.append(
            ATSIssue(code='location', severity='low', message='No location/city detected near contact details')
        )
        deductions += 3

    if experience_count or experience_heading:
        if not _experience_has_dates(structured, text):
            issues.append(
                ATSIssue(
                    code='missing_dates',
                    severity='medium',
                    message='Experience entries lack clear start/end dates (year ranges help ATS ranking)',
                )
            )
            deductions += 8

    if text and not _has_metrics(text):
        issues.append(
            ATSIssue(
                code='no_metrics',
                severity='low',
                message='Few measurable achievements (numbers/%); ATS-friendly CVs usually quantify impact',
            )
        )
        deductions += 5

    word_count = len(re.findall(r'\b\w+\b', text))
    if word_count < 120:
        issues.append(
            ATSIssue(
                code='too_short',
                severity='high',
                message=f'CV text is very short ({word_count} words); ATS may under-index content',
            )
        )
        deductions += 15
    elif word_count > 1200:
        issues.append(
            ATSIssue(
                code='too_long',
                severity='low',
                message=f'CV text is long ({word_count} words); consider tightening for ATS scanners',
            )
        )
        deductions += 5

    # Heuristic: dense non-alphanumeric / pipe-table layouts often break ATS parsers
    if text:
        special_ratio = len(re.findall(r'[|▪●◆■□★☆►❖]', text)) / max(len(text), 1)
        if special_ratio > 0.008:
            issues.append(
                ATSIssue(
                    code='special_chars',
                    severity='medium',
                    message='Heavy use of special symbols/bullets/tables that some ATS parsers mishandle',
                )
            )
            deductions += 10
        pipe_lines = sum(1 for line in text.splitlines() if line.count('|') >= 2)
        if pipe_lines >= 2:
            issues.append(
                ATSIssue(
                    code='table_layout',
                    severity='medium',
                    message='Table-like pipe columns detected; multi-column layouts often break ATS parsers',
                )
            )
            deductions += 8

    if filename and not filename.lower().endswith('.pdf'):
        issues.append(
            ATSIssue(code='file_format', severity='high', message='Non-PDF formats are often poorly parsed by ATS')
        )
        deductions += 10

    score = max(0, min(100, 100 - deductions))
    # Cap perfect scores unless the CV passes a strong baseline of text-visible structure
    strong_baseline = email_in_text and skills_heading and experience_heading and education_heading and word_count >= 120
    if score >= 98 and not strong_baseline:
        score = min(score, 92)
        if not any(i.code == 'baseline_cap' for i in issues):
            issues.append(
                ATSIssue(
                    code='baseline_cap',
                    severity='low',
                    message='Score capped: CV needs clearer text-visible contact + Skills/Experience/Education headings for a top ATS score',
                )
            )

    return ATSResult(score=score, issues=issues)
