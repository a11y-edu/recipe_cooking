# Accessible Recipe Prototype

Local Streamlit prototype for researching how to convert sighted-oriented recipes into formats that work better for blind and low-vision cooks.

## What This App Does

- Loads 200 scraped recipes from `Pilot Coding Worksheet Structure (v1.1).xlsx`.
- Lets users search recipes by title from the left sidebar.
- Shows three panels for the selected recipe:
  - Panel 1: canonical recipe with visual-descriptor highlights from `Descriptor_Coding`.
  - Panel 2: placeholder non-visual conversion panel that currently mirrors Panel 1 while preserving a future transformation interface.
  - Panel 3: recipe-scoped chatbot using Streamlit chat UI plus OpenRouter embeddings and chat completions.
- Logs anonymous preference clicks from Panels 1 and 2 to `local_data/feedback_events.jsonl`.
- Caches embeddings locally in `local_data/embedding_cache.pkl`.
- Saves sidebar corpus analytics to `local_data/corpus_insights.json`.

## Current Research Constraints

- `Descriptor_Coding` is the authoritative VDD sheet for v1.
- `Descriptor_Coding-56rec` is intentionally ignored unless a later task explicitly asks for comparison work.
- Panel 2 is not a real conversion yet. It exists to keep the UI and preference logging stable while the non-visual rewriting method is still being designed.
- Free OpenRouter endpoints may log prompts, so do not send participant identifiers or sensitive data.

## Quick Start

1. Install dependencies:

```bash
python3 -m pip install -r /Users/smb/Documents/code/recipe_cooking/requirements.txt
```

2. Configure environment variables:

```bash
cp /Users/smb/Documents/code/recipe_cooking/.env.example /Users/smb/Documents/code/recipe_cooking/.env
```

Required values in `.env`:

- `OPENROUTER_API_KEY`
- `OPENROUTER_CHAT_MODEL`
- `OPENROUTER_EMBED_MODEL`
- `RECIPE_WORKBOOK_PATH`

3. Run the app:

```bash
streamlit run /Users/smb/Documents/code/recipe_cooking/app.py
```

## Validation

Run the core checks before and after substantial changes:

```bash
pytest -q
python3 -m compileall app.py recipe_app tests
```

## Project Layout

- [`app.py`](/Users/smb/Documents/code/recipe_cooking/app.py): Streamlit entrypoint and UI flow.
- [`recipe_app/data_loader.py`](/Users/smb/Documents/code/recipe_cooking/recipe_app/data_loader.py): Workbook ingestion, canonical recipe assembly, chunk building.
- [`recipe_app/highlighting.py`](/Users/smb/Documents/code/recipe_cooking/recipe_app/highlighting.py): Descriptor span matching and fallback marker rendering.
- [`recipe_app/transforms.py`](/Users/smb/Documents/code/recipe_cooking/recipe_app/transforms.py): Placeholder transformation interface for Panel 2.
- [`recipe_app/rag.py`](/Users/smb/Documents/code/recipe_cooking/recipe_app/rag.py): OpenRouter-backed recipe-scoped retrieval and chat.
- [`recipe_app/feedback.py`](/Users/smb/Documents/code/recipe_cooking/recipe_app/feedback.py): Anonymous preference event logging.
- [`tests/test_app_core.py`](/Users/smb/Documents/code/recipe_cooking/tests/test_app_core.py): Ingestion, highlighting, feedback, and transform tests.

## Prompt Starters For Future Codex Sessions

For future work, point Codex to the project skill at [`skills/accessible-recipe-research/SKILL.md`](/Users/smb/Documents/code/recipe_cooking/skills/accessible-recipe-research/SKILL.md) first.

Useful prompts:

- "Use the project skill and add filtering by category in the sidebar."
- "Use the project skill and replace the placeholder transformation with a rule-based baseline."
- "Use the project skill and add exportable analytics for feedback events."
- "Use the project skill and evaluate whether the retrieval chunks are optimal for cooking questions."

## Security Notes

- Do not hardcode or print the OpenRouter API key.
- `.env` should remain local only.
- Runtime-generated files under `local_data/` should be treated as research artifacts, not committed source files.
