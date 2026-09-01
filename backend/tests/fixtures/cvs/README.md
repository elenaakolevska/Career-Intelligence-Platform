# Sample CV fixtures for Phase 2–3 testing and paper evaluation.

Synthetic / anonymized only — no real personal data.

## Contents

| File | Format | Notes |
|------|--------|-------|
| `junior_backend.txt` | text | Junior Python/backend profile |
| `senior_fullstack.txt` | text | Senior full-stack profile |
| `data_scientist.txt` | text | Mid-level data science |
| `career_switcher.txt` | text | Non-traditional path, sparse tech |
| `ats_problematic.txt` | text | Symbol-heavy, missing sections |
| `ats_clean.txt` | text | Clean ATS-friendly layout |
| `scanned_note.txt` | text | Placeholder describing scanned PDF |
| `generate_pdfs.py` | script | Builds PDFs under `pdfs/` including image-only OCR sample |

Generate PDFs:

```bash
cd backend
python ../tests/fixtures/cvs/generate_pdfs.py
```

Automated tests reference these fixtures via `tests/fixtures/cvs/`.
