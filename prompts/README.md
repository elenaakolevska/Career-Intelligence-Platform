# Prompt templates

Prompt files are plain UTF-8 text loaded at runtime (never inlined in Python).

## Naming

- `{domain}_{purpose}_prompt.txt` — e.g. `cv_extraction_prompt.txt`, `skill_gap_prompt.txt`
- Placeholders use `{{NAME}}` double-brace syntax

## RAG templates (Phase 5)

| File | Placeholders | Task |
|------|--------------|------|
| `market_trends_prompt.txt` | `{{CONTEXT}}`, `{{PROFILE}}`, `{{QUESTION}}` | In-demand skills from retrieved jobs |
| `skill_gap_prompt.txt` | `{{CONTEXT}}`, `{{PROFILE}}`, `{{QUESTION}}` | Prioritized gaps vs market context |
| `learning_roadmap_prompt.txt` | `{{CONTEXT}}`, `{{PROFILE}}`, `{{QUESTION}}` | 30/60/90-day plan from resources |
| `cv_extraction_prompt.txt` | `{{CV_TEXT}}` | Structured CV JSON extraction |
| `interview_question_prompt.txt` | `{{TARGET_ROLE}}`, `{{DIFFICULTY}}`, `{{SENIORITY_CONTEXT}}`, `{{PREVIOUS_QUESTIONS}}`, `{{VARIATION_SEED}}` | Role-specific technical interview question (P7-02) |
| `interview_eval_prompt.txt` | `{{TARGET_ROLE}}`, `{{DIFFICULTY}}`, `{{QUESTION}}`, `{{ANSWER}}` | Score + written feedback for an answer (P7-03 / §8.5) |

All RAG templates instruct: answer only from context; hedge when context is empty.

## Loading

Backend resolves prompts relative to the repo `prompts/` directory (or `PROMPTS_DIR`).
Use `app.services.prompt_loader.render_prompt(name, **placeholders)`.
