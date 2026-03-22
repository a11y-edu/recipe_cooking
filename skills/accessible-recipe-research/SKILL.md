---
name: accessible-recipe-research
description: Use when working on the accessible recipe Streamlit prototype in this repo. Covers Excel-based recipe ingestion, visual descriptor highlighting, placeholder non-visual conversion, anonymous preference logging, and recipe-scoped OpenRouter RAG chat. Use for feature work, bug fixes, research iteration, evaluation, and prompt/session continuity for this project.
---

# Accessible Recipe Research

## Use This Skill When

- The task is about this repository's Streamlit app, recipe data model, VDD highlighting, feedback logging, or chatbot.
- You need continuity with the project's current research assumptions.
- You want future prompts to avoid re-explaining the repo every time.

## First Pass

1. Read `README.md` for setup and current behavior.
2. Inspect these files first:
   - `app.py`
   - `recipe_app/data_loader.py`
   - `recipe_app/highlighting.py`
   - `recipe_app/rag.py`
   - `tests/test_app_core.py`

## Project Guardrails

- Treat `Descriptor_Coding` as the authoritative VDD source for v1.
- Ignore `Descriptor_Coding-56rec` unless the task explicitly asks for comparison or migration work.
- Keep `TransformationService.transform(recipe)` stable unless the task is specifically about redesigning the conversion interface.
- Keep chatbot retrieval scoped to the currently selected recipe.
- Preserve the Streamlit chat-thread UX unless the task explicitly redesigns chat.
- Never hardcode, echo, or commit secrets from `.env`.
- Do not send participant identifiers or other sensitive data to OpenRouter free endpoints.
- Preserve anonymous preference logging to `local_data/feedback_events.jsonl` unless the task explicitly changes the study protocol.

## Default Validation

Run:

```bash
pytest -q
python3 -m compileall app.py recipe_app tests
```

If the task affects the running app, also do a brief local `streamlit run app.py` smoke test when practical.

## For More Detail

Read `references/project-context.md` for architecture notes, known limitations, and likely next-step tasks.
