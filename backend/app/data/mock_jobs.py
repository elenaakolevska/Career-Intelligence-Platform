"""Static mock job postings matching the normalized JobPosting schema.

Includes:
- North Macedonia / local-market corpus (thesis demo when Adzuna has no MK market)
- UK / general corpus (also used as Adzuna offline fallback)

Set ``ADZUNA_USE_MOCK=true`` to exercise the full pipeline on this corpus.
Live UK jobs still use Adzuna when ``ADZUNA_USE_MOCK=false`` and credentials are set.
"""

from __future__ import annotations

from typing import Any

# --- North Macedonia local-market corpus (Skopje / Ohrid / remote-MK) ---
MK_MOCK_JOBS: list[dict] = [
    {
        'title': 'Junior Java Developer',
        'company': 'Seavus',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Junior Java developer for enterprise web apps. Spring Boot, Spring Security, '
            'PostgreSQL, Git, REST APIs. Mentorship for graduates and students.'
        ),
        'url': 'https://example.mk/jobs/junior-java-skopje',
        'salary_min': 9000,
        'salary_max': 14000,
        'salary_raw': '750-1150 EUR/month',
        'external_id': 'mock-mk-1',
        'source': 'mock-mk',
    },
    {
        'title': 'Junior Spring Boot Developer',
        'company': 'Netcetera',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Build backend services with Java, Spring Boot, Thymeleaf, PostgreSQL, Docker. '
            'Entry-level role with code reviews and Agile/Scrum.'
        ),
        'url': 'https://example.mk/jobs/junior-spring-skopje',
        'salary_min': 10000,
        'salary_max': 15000,
        'salary_raw': '800-1250 EUR/month',
        'external_id': 'mock-mk-2',
        'source': 'mock-mk',
    },
    {
        'title': 'Junior Full Stack Developer (Java + React)',
        'company': 'Innovation Dooel',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Full-stack product work: Java Spring Boot APIs, React, JavaScript, HTML/CSS, '
            'PostgreSQL, Git. Suitable for students finishing Applied Information Technologies.'
        ),
        'url': 'https://example.mk/jobs/fullstack-java-react',
        'salary_min': 9500,
        'salary_max': 14500,
        'salary_raw': '800-1200 EUR/month',
        'external_id': 'mock-mk-3',
        'source': 'mock-mk',
    },
    {
        'title': 'Junior React Frontend Developer',
        'company': 'IWConnect',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Frontend role with React, JavaScript, HTML, CSS, Bootstrap, Git. '
            'Collaborate with Java backend teams on REST integrations.'
        ),
        'url': 'https://example.mk/jobs/junior-react-skopje',
        'salary_min': 8500,
        'salary_max': 13000,
        'salary_raw': '700-1100 EUR/month',
        'external_id': 'mock-mk-4',
        'source': 'mock-mk',
    },
    {
        'title': 'Python Developer (Junior)',
        'company': 'CodeLabs MK',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Junior Python developer: Django or FastAPI, PostgreSQL, Pandas, NumPy, Git, Docker. '
            'Data-aware web features and internal tools.'
        ),
        'url': 'https://example.mk/jobs/junior-python-skopje',
        'salary_min': 9000,
        'salary_max': 14000,
        'salary_raw': '750-1150 EUR/month',
        'external_id': 'mock-mk-5',
        'source': 'mock-mk',
    },
    {
        'title': '.NET Junior Developer',
        'company': 'MakPetrol IT Partner',
        'location': 'Skopje, North Macedonia',
        'description': (
            'ASP.NET Core, C#, Entity Framework, SQL Server/PostgreSQL, HTML/CSS, JavaScript. '
            'Graduate-friendly MVC web applications.'
        ),
        'url': 'https://example.mk/jobs/junior-dotnet-skopje',
        'salary_min': 9000,
        'salary_max': 13500,
        'salary_raw': '750-1100 EUR/month',
        'external_id': 'mock-mk-6',
        'source': 'mock-mk',
    },
    {
        'title': 'Internship — Software Engineering',
        'company': 'FINKI Career Hub Partner',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Paid internship for CS students. Java or Python, Spring Boot or Django, SQL, Git, '
            'Agile. Mentored delivery on real product tickets.'
        ),
        'url': 'https://example.mk/jobs/internship-software-skopje',
        'salary_min': 4000,
        'salary_max': 7000,
        'salary_raw': '300-550 EUR/month',
        'external_id': 'mock-mk-7',
        'source': 'mock-mk',
    },
    {
        'title': 'Junior Backend Developer (Remote MK)',
        'company': 'Balkan Soft Remote',
        'location': 'Remote, North Macedonia',
        'description': (
            'Remote-friendly junior backend role for candidates in North Macedonia. '
            'Java Spring Boot, PostgreSQL, Docker, REST, Git. English C1 required.'
        ),
        'url': 'https://example.mk/jobs/remote-junior-backend-mk',
        'salary_min': 11000,
        'salary_max': 16000,
        'salary_raw': '900-1300 EUR/month',
        'external_id': 'mock-mk-8',
        'source': 'mock-mk',
    },
    {
        'title': 'Web Developer — Student Projects & Products',
        'company': 'Ohrid Digital Studio',
        'location': 'Ohrid, North Macedonia',
        'description': (
            'Hybrid web role in Ohrid: JavaScript, React, HTML/CSS, Bootstrap, basic Java or C#, '
            'PostgreSQL, Git. Good fit for students with project portfolios.'
        ),
        'url': 'https://example.mk/jobs/web-ohrid',
        'salary_min': 7000,
        'salary_max': 11000,
        'salary_raw': '550-900 EUR/month',
        'external_id': 'mock-mk-9',
        'source': 'mock-mk',
    },
    {
        'title': 'Junior QA / Automation Tester',
        'company': 'Axway Skopje',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Manual and automated testing for web apps. Java or Python, Selenium or Playwright, '
            'Git, CI pipelines, Agile. Junior or graduate level.'
        ),
        'url': 'https://example.mk/jobs/junior-qa-skopje',
        'salary_min': 8000,
        'salary_max': 12000,
        'salary_raw': '650-1000 EUR/month',
        'external_id': 'mock-mk-10',
        'source': 'mock-mk',
    },
    {
        'title': 'Junior DevOps / Platform Support',
        'company': 'Cloud MK Solutions',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Support containerized apps: Docker, Linux, Git, CI/CD basics, monitoring. '
            'Python or Bash scripting. Exposure to AWS or Azure is a plus.'
        ),
        'url': 'https://example.mk/jobs/junior-devops-skopje',
        'salary_min': 9500,
        'salary_max': 14500,
        'salary_raw': '800-1200 EUR/month',
        'external_id': 'mock-mk-11',
        'source': 'mock-mk',
    },
    {
        'title': 'Graduate Software Engineer — Java Ecosystem',
        'company': 'Endava',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Graduate program: Java, Spring Boot, microservices, SQL, Git, Agile/Scrum, '
            'REST APIs. Strong mentoring and English working environment.'
        ),
        'url': 'https://example.mk/jobs/graduate-java-endava',
        'salary_min': 10000,
        'salary_max': 15000,
        'salary_raw': '850-1250 EUR/month',
        'external_id': 'mock-mk-12',
        'source': 'mock-mk',
    },
    {
        'title': 'Junior Data / ML Enthusiast (Part-time)',
        'company': 'InnoLab Skopje',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Part-time role for students: Python, Pandas, NumPy, OpenCV or Machine Learning basics, '
            'Git. Raspberry Pi / Arduino project experience welcome.'
        ),
        'url': 'https://example.mk/jobs/junior-ml-skopje',
        'salary_min': 5000,
        'salary_max': 9000,
        'salary_raw': '400-750 EUR/month',
        'external_id': 'mock-mk-13',
        'source': 'mock-mk',
    },
    {
        'title': 'Junior C# / ASP.NET MVC Developer',
        'company': 'NextSense',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Maintain and extend ASP.NET Core MVC apps with C#, Entity Framework, SQL, '
            'HTML/CSS/JavaScript, Git. Junior applicants with project experience encouraged.'
        ),
        'url': 'https://example.mk/jobs/junior-csharp-skopje',
        'salary_min': 9000,
        'salary_max': 14000,
        'salary_raw': '750-1150 EUR/month',
        'external_id': 'mock-mk-14',
        'source': 'mock-mk',
    },
    {
        'title': 'Software Engineer Intern — Student Connect style products',
        'company': 'Campus Tech MK',
        'location': 'Skopje, North Macedonia',
        'description': (
            'Internship building listing/marketplace features: Java Spring Boot, Thymeleaf, '
            'PostgreSQL, Spring Security, Git. Ideal for students with similar project portfolios.'
        ),
        'url': 'https://example.mk/jobs/intern-campus-tech',
        'salary_min': 4500,
        'salary_max': 7500,
        'salary_raw': '350-600 EUR/month',
        'external_id': 'mock-mk-15',
        'source': 'mock-mk',
    },
]

# --- UK / general offline corpus (Adzuna fallback + international variety) ---
UK_MOCK_JOBS: list[dict] = [
    {
        'title': 'Backend Software Engineer',
        'company': 'Nimbus Labs',
        'location': 'London, UK',
        'description': 'Build Python FastAPI services, PostgreSQL, Redis, Docker. 3+ years experience.',
        'url': 'https://example.com/jobs/1',
        'salary_min': 55000,
        'salary_max': 75000,
        'salary_raw': '55000-75000',
        'external_id': 'mock-1',
        'source': 'mock',
    },
    {
        'title': 'Junior Python Developer',
        'company': 'BrightStart',
        'location': 'Manchester, UK',
        'description': 'Entry-level Python role with mentorship. REST APIs, SQL, Git.',
        'url': 'https://example.com/jobs/2',
        'salary_min': 32000,
        'salary_max': 42000,
        'salary_raw': '32000-42000',
        'external_id': 'mock-2',
        'source': 'mock',
    },
    {
        'title': 'Full Stack Engineer',
        'company': 'Orbit Digital',
        'location': 'Remote, UK',
        'description': 'React, TypeScript, Node.js, PostgreSQL. End-to-end product features.',
        'url': 'https://example.com/jobs/3',
        'salary_min': 50000,
        'salary_max': 70000,
        'salary_raw': '50000-70000',
        'external_id': 'mock-3',
        'source': 'mock',
    },
    {
        'title': 'Data Engineer',
        'company': 'Lakehouse Analytics',
        'location': 'Edinburgh, UK',
        'description': 'ETL pipelines, Spark, Python, Airflow, cloud data warehouses.',
        'url': 'https://example.com/jobs/4',
        'salary_min': 60000,
        'salary_max': 85000,
        'salary_raw': '60000-85000',
        'external_id': 'mock-4',
        'source': 'mock',
    },
    {
        'title': 'ML Engineer',
        'company': 'VectorAI',
        'location': 'Cambridge, UK',
        'description': 'Deploy ML models, PyTorch, sentence-transformers, MLOps, FAISS.',
        'url': 'https://example.com/jobs/5',
        'salary_min': 65000,
        'salary_max': 90000,
        'salary_raw': '65000-90000',
        'external_id': 'mock-5',
        'source': 'mock',
    },
    {
        'title': 'DevOps Engineer',
        'company': 'CloudForge',
        'location': 'Bristol, UK',
        'description': 'Kubernetes, Terraform, AWS, CI/CD, observability.',
        'url': 'https://example.com/jobs/6',
        'salary_min': 58000,
        'salary_max': 80000,
        'salary_raw': '58000-80000',
        'external_id': 'mock-6',
        'source': 'mock',
    },
    {
        'title': 'Frontend Engineer',
        'company': 'Pixel & Co',
        'location': 'London, UK',
        'description': 'React, Tailwind, Vite, accessibility, design systems.',
        'url': 'https://example.com/jobs/7',
        'salary_min': 48000,
        'salary_max': 68000,
        'salary_raw': '48000-68000',
        'external_id': 'mock-7',
        'source': 'mock',
    },
    {
        'title': 'Platform Engineer',
        'company': 'Stackyard',
        'location': 'Leeds, UK',
        'description': 'Internal developer platforms, Docker, Kubernetes, Python tooling.',
        'url': 'https://example.com/jobs/8',
        'salary_min': 62000,
        'salary_max': 88000,
        'salary_raw': '62000-88000',
        'external_id': 'mock-8',
        'source': 'mock',
    },
    {
        'title': 'AI Application Engineer',
        'company': 'PromptWorks',
        'location': 'Remote, EU',
        'description': 'LLM apps, RAG pipelines, LangGraph, FastAPI, evaluation harnesses.',
        'url': 'https://example.com/jobs/9',
        'salary_min': 70000,
        'salary_max': 95000,
        'salary_raw': '70000-95000',
        'external_id': 'mock-9',
        'source': 'mock',
    },
    {
        'title': 'Security Engineer',
        'company': 'ShieldByte',
        'location': 'London, UK',
        'description': 'Application security, threat modeling, Python automation, SIEM.',
        'url': 'https://example.com/jobs/10',
        'salary_min': 65000,
        'salary_max': 90000,
        'salary_raw': '65000-90000',
        'external_id': 'mock-10',
        'source': 'mock',
    },
]

_EXTRA_ROLES = [
    ('Senior Backend Engineer', 'Python, FastAPI, microservices, PostgreSQL'),
    ('Graduate Software Engineer', 'Java, Spring Boot, SQL, Git'),
    ('Cloud Engineer', 'AWS, Azure, IaC, networking'),
    ('QA Automation Engineer', 'Pytest, Selenium, CI pipelines'),
    ('Mobile Engineer', 'React Native, TypeScript, mobile UX'),
    ('Site Reliability Engineer', 'SRE, Prometheus, Kubernetes, on-call'),
    ('Analytics Engineer', 'dbt, SQL, Looker, data modeling'),
    ('NLP Engineer', 'Transformers, spaCy, evaluation, Python'),
    ('Solutions Engineer', 'Customer integrations, APIs, demos'),
    ('Technical Support Engineer', 'Linux, networking, scripting, tickets'),
    ('Database Administrator', 'PostgreSQL, backups, performance tuning'),
    ('Integration Engineer', 'REST, webhooks, ETL, Python'),
    ('Rust Engineer', 'Rust, systems programming, concurrency'),
    ('Go Engineer', 'Go, gRPC, distributed systems'),
    ('Product Engineer', 'Full-stack delivery, React, Python APIs'),
    ('Research Engineer', 'Prototyping, ML papers, PyTorch'),
    ('Automation Engineer', 'RPA, Python scripting, process tooling'),
    ('API Engineer', 'OpenAPI, FastAPI, auth, rate limits'),
    ('Infrastructure Engineer', 'Terraform, Ansible, cloud networking'),
    ('Growth Engineer', 'Experimentation, analytics events, web apps'),
]

for idx, (title, skills) in enumerate(_EXTRA_ROLES, start=11):
    UK_MOCK_JOBS.append(
        {
            'title': title,
            'company': f'Company {idx}',
            'location': 'UK',
            'description': f'{title} role focusing on {skills}.',
            'url': f'https://example.com/jobs/{idx}',
            'salary_min': 40000 + (idx * 500),
            'salary_max': 60000 + (idx * 500),
            'salary_raw': None,
            'external_id': f'mock-{idx}',
            'source': 'mock',
        }
    )

# Full offline corpus: MK first so default fetch slices favour the local-market narrative
MOCK_JOBS: list[dict] = list(MK_MOCK_JOBS) + list(UK_MOCK_JOBS)

_MK_LOCATION_MARKERS = (
    'macedonia',
    'skopje',
    'ohrid',
    'bitola',
    'tetovo',
    'prilep',
    'mk',
)


def cv_prefers_macedonia_market(structured: dict[str, Any] | None) -> bool:
    structured = structured or {}
    blob = ' '.join(
        [
            str(structured.get('location') or ''),
            ' '.join(str((e or {}).get('location') or '') for e in (structured.get('experience') or [])),
            ' '.join(str((e or {}).get('location') or '') for e in (structured.get('education') or [])),
        ]
    ).lower()
    return any(marker in blob for marker in _MK_LOCATION_MARKERS)


def select_mock_jobs_for_profile(
    structured: dict[str, Any] | None,
    *,
    limit: int = 20,
) -> list[dict]:
    """Prefer MK postings for MK CVs; otherwise return a mixed/UK-leaning slice."""
    if limit <= 0:
        return []
    if cv_prefers_macedonia_market(structured):
        # MK corpus first, then fill with UK juniors if needed
        selected = list(MK_MOCK_JOBS)
        if len(selected) < limit:
            selected.extend(UK_MOCK_JOBS)
        return selected[:limit]
    # International / UK demo: skip MK block so results look Adzuna-like
    return list(UK_MOCK_JOBS)[:limit]
