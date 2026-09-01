"""Shared skill vocabulary + matching helpers for market/gap agents."""

from __future__ import annotations

import re
from typing import Iterable

# Canonical skill lexicon used to scan job text (MVP; extend as needed)
SKILL_LEXICON: list[str] = [
    'Python',
    'Java',
    'JavaScript',
    'TypeScript',
    'Go',
    'Rust',
    'C#',
    'C++',
    'SQL',
    'PostgreSQL',
    'MySQL',
    'MongoDB',
    'Redis',
    'FastAPI',
    'Django',
    'Flask',
    'Spring Boot',
    'Spring',
    '.NET',
    'ASP.NET',
    'React',
    'Vue',
    'Angular',
    'Node.js',
    'Docker',
    'Kubernetes',
    'AWS',
    'Azure',
    'GCP',
    'Terraform',
    'Linux',
    'Git',
    'CI/CD',
    'Airflow',
    'Spark',
    'Pandas',
    'PyTorch',
    'TensorFlow',
    'NLP',
    'RAG',
    'LangGraph',
    'FAISS',
    'REST',
    'GraphQL',
    'Kafka',
    'RabbitMQ',
    'Elasticsearch',
    'Prometheus',
    'Grafana',
    'Ansible',
    'Helm',
    'HTML',
    'CSS',
    'Agile',
    'Scrum',
    'microservices',
    'API',
    'security',
    'Embedded Systems',
    'OpenCV',
    'Machine Learning',
]

# Map aliases / variants → canonical lexicon name
SKILL_ALIASES: dict[str, str] = {
    'js': 'JavaScript',
    'javascript': 'JavaScript',
    'ts': 'TypeScript',
    'typescript': 'TypeScript',
    'node': 'Node.js',
    'nodejs': 'Node.js',
    'node.js': 'Node.js',
    'k8s': 'Kubernetes',
    'kubernetes': 'Kubernetes',
    'postgres': 'PostgreSQL',
    'postgresql': 'PostgreSQL',
    'psql': 'PostgreSQL',
    'mongo': 'MongoDB',
    'mongodb': 'MongoDB',
    'py': 'Python',
    'python': 'Python',
    'fastapi': 'FastAPI',
    'django': 'Django',
    'flask': 'Flask',
    'spring boot': 'Spring Boot',
    'springboot': 'Spring Boot',
    'spring': 'Spring',
    'dotnet': '.NET',
    '.net': '.NET',
    'asp.net': 'ASP.NET',
    'aspnet': 'ASP.NET',
    'reactjs': 'React',
    'react': 'React',
    'docker': 'Docker',
    'aws': 'AWS',
    'azure': 'Azure',
    'microsoft azure': 'Azure',
    'gcp': 'GCP',
    'google cloud': 'GCP',
    'tf': 'Terraform',
    'terraform': 'Terraform',
    'cicd': 'CI/CD',
    'ci/cd': 'CI/CD',
    'ci-cd': 'CI/CD',
    'pytorch': 'PyTorch',
    'tensorflow': 'TensorFlow',
    'langgraph': 'LangGraph',
    'faiss': 'FAISS',
    'sql': 'SQL',
    'rest': 'REST',
    'rest api': 'REST',
    'restful': 'REST',
    'golang': 'Go',
    'go lang': 'Go',
    'c sharp': 'C#',
    'csharp': 'C#',
    'cpp': 'C++',
    'c plus plus': 'C++',
    'ml': 'Machine Learning',
    'machine learning': 'Machine Learning',
    'microservice': 'microservices',
    'microservices': 'microservices',
    'appsec': 'security',
    'application security': 'security',
    'penetration testing': 'security',
    'pen testing': 'security',
    'embedded': 'Embedded Systems',
    'embedded systems': 'Embedded Systems',
    'embedded system': 'Embedded Systems',
    'embedded software': 'Embedded Systems',
    'embedded development': 'Embedded Systems',
}


def normalize_skill_key(skill: str) -> str:
    return re.sub(r'[^a-z0-9+#./]+', ' ', (skill or '').lower()).strip()


def canonicalize_skill(skill: str) -> str:
    key = normalize_skill_key(skill)
    if not key:
        return skill.strip()
    if key in SKILL_ALIASES:
        return SKILL_ALIASES[key]
    # Title-case fallback matching lexicon ignore-case
    for canon in SKILL_LEXICON:
        if normalize_skill_key(canon) == key:
            return canon
    return skill.strip()


def extract_skills_from_text(text: str) -> list[str]:
    """Return canonical skills mentioned in text (order-preserving, unique)."""
    if not text:
        return []
    lowered = text.lower()
    found: list[str] = []
    seen: set[str] = set()

    # Match aliases + lexicon; longer phrases first (e.g. Spring Boot before Spring)
    phrases: list[tuple[str, str]] = []
    for alias, canon in SKILL_ALIASES.items():
        phrases.append((alias, canon))
    for skill in SKILL_LEXICON:
        phrases.append((skill.lower(), skill))
    phrases.sort(key=lambda p: len(p[0]), reverse=True)

    for phrase, canon in phrases:
        pattern = r'(?<![a-z0-9])' + re.escape(phrase) + r'(?![a-z0-9])'
        if re.search(pattern, lowered) and canon not in seen:
            seen.add(canon)
            found.append(canon)
    return found


def candidate_skill_set(skills: Iterable[str]) -> set[str]:
    return {canonicalize_skill(s) for s in skills if str(s).strip()}


def skills_match(market_skill: str, candidate_skills: set[str]) -> bool:
    """Semantic-ish match: canonical equality, alias, or substring containment."""
    target = canonicalize_skill(market_skill)
    target_key = normalize_skill_key(target)
    for owned in candidate_skills:
        owned_canon = canonicalize_skill(owned)
        if owned_canon == target:
            return True
        owned_key = normalize_skill_key(owned_canon)
        if not owned_key or not target_key:
            continue
        if owned_key == target_key:
            return True
        # containment for close variants (e.g. "react native" vs "React")
        if target_key in owned_key or owned_key in target_key:
            if min(len(owned_key), len(target_key)) >= 3:
                return True
    return False
