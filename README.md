# Accessible Recipe Prototype

Local Streamlit prototype for researching how to convert sighted-oriented recipes into formats that work better for blind and low-vision cooks.

## What This App Does

- Loads 200 scraped recipes from `Pilot Coding Worksheet Structure (v1.1).xlsx`.
- Lets users search recipes by title from the left sidebar.
- Adds sidebar database tools for resetting the app tables from Excel, adding a manual recipe, and exporting stored recipes as JSON.
- Shows three panels for the selected recipe:
  - Panel 1: canonical recipe with visual-descriptor highlights from `Descriptor_Coding`.
- Panel 2: placeholder non-visual conversion panel that currently mirrors Panel 1 while preserving a future transformation interface.
  - Panel 3: recipe-scoped chatbot using Streamlit chat UI plus OpenRouter embeddings and chat completions.
- Logs anonymous preference clicks from Panels 1 and 2 to Supabase when configured, with local JSONL fallback at `local_data/feedback_events.jsonl`.
- Caches embeddings locally in `local_data/embedding_cache.pkl` only when Supabase is not configured.
- Saves sidebar corpus analytics to `local_data/corpus_insights.json`.
- Can seed recipes into Supabase, read recipes back from Supabase, and store chunk embeddings there for recipe retrieval.
- Exports both recipe versions plus per-version vote counts from `feedback_events`.

## Current Research Constraints

- `Descriptor_Coding` is the authoritative VDD sheet for v1.
- `Descriptor_Coding-56rec` is intentionally ignored unless a later task explicitly asks for comparison work.
- Panel 2 uses workbook version-2 fields when those columns exist; otherwise it defaults to the same content as Version 1.
- Free OpenRouter endpoints may log prompts, so do not send participant identifiers or sensitive data.

## Workbook Version 2 Columns

If you want the loader to import distinct Version 2 recipe text from the Excel workbook, add optional Version 2 columns to these sheets:

- `Ingredients_List`
  Use one of these header names for the Version 2 ingredient text column:
  - `Version_2_Ingredient_Text`
  - `Full_Ingredient_Text_Version_2`
  - `Full_Ingredient_Text_V2`
  - `Ingredient_Text_Version_2`
- `Procedural_Text`
  Use one of these header names for the Version 2 step-sentence text column:
  - `Version_2_Sentence_Text`
  - `Full_Sentence_Text_Version_2`
  - `Full_Sentence_Text_V2`
  - `Sentence_Text_Version_2`

Notes:

- The Version 2 columns can be added anywhere in those sheets. The loader matches by header name, not fixed column position.
- `Ingredients_List` Version 2 rows are matched by the existing `Recipe_ID` and `Ingredient_Line_Number`.
- `Procedural_Text` Version 2 rows are matched by the existing `Recipe_ID`, `Step_Number`, and `Sentence_Number`.
- If those Version 2 columns are missing or blank for a recipe, the app defaults Version 2 to the same ingredients and steps as Version 1.
- No Version 2 columns are currently read from `Recipe_Metadata` or `Descriptor_Coding`.

## Quick Start

1. Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

2. Configure environment variables:

```bash
cp .env.example .env
```

Required values in `.env`:

- `OPENROUTER_API_KEY`
- `OPENROUTER_CHAT_MODEL`
- `OPENROUTER_EMBED_MODEL`
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY` recommended
- or legacy `SUPABASE_SERVICE_ROLE_KEY`
- or `SUPABASE_ANON_KEY` if you have explicit RLS policies for the required reads/writes
- `RECIPE_WORKBOOK_PATH` for the first sync if your Supabase tables are still empty

3. Run the app:

```bash
streamlit run app.py
```

## Validation

Run the core checks before and after substantial changes:

```bash
pytest -q
python3 -m compileall app.py recipe_app tests
```

## Supabase Setup

1. In your Supabase SQL editor, run `supabase/schema.sql`.
2. Add `SUPABASE_URL` and `SUPABASE_SECRET_KEY` to `.env` or Streamlit secrets.
   The app also accepts the legacy `SUPABASE_SERVICE_ROLE_KEY`, or `SUPABASE_ANON_KEY` if you are relying on RLS policies.
3. Start the app. If the `recipes` table is empty and the workbook is present locally, the app will seed Supabase automatically.
4. After the first sync, the app can read recipe content back from Supabase even if the workbook is no longer present on disk.
5. Chunk embeddings are created on demand and stored in `recipe_chunks`.
6. Preference clicks are stored in `feedback_events`. If the Supabase write fails, the app falls back to `local_data/feedback_events.jsonl`.

## Sidebar Database Tools

- `Reset`: clears the app-managed recipe tables in Supabase and reseeds them from the Excel workbook.
- `Add recipe`: opens a sidebar form for a manual recipe ID, title, category, optional URL and ratings, plus newline-separated ingredients and steps for both versions.
- `Export`: downloads JSON with recipe metadata, both versions, and version-specific vote counts.

Notes:

- The workbook is only needed as the local seed source for the first sync or when you want to refresh the database from the spreadsheet.
- Once configured, the app reads recipe content from Supabase and reads/writes chunk embeddings there.
- A secret key is the simplest option. If you use an anon key instead, your Supabase RLS policies must allow the required reads and writes.
- Keep the secret key in server-side secrets only.
- If you want to persist distinct Version 2 content in Supabase, rerun `supabase/schema.sql` so the `version_2_ingredients` and `version_2_steps` columns are added to `public.recipes`.

## Project Layout

- `app.py`: Streamlit entrypoint and UI flow.
- `recipe_app/data_loader.py`: Workbook ingestion, canonical recipe assembly, chunk building.
- `recipe_app/highlighting.py`: Descriptor span matching and fallback marker rendering.
- `recipe_app/transforms.py`: Placeholder transformation interface for Panel 2.
- `recipe_app/rag.py`: OpenRouter-backed recipe-scoped retrieval and chat.
- `recipe_app/feedback.py`: Anonymous preference event logging with Supabase-first persistence.
- `tests/test_app_core.py`: Ingestion, highlighting, feedback, and transform tests.

## Prompt Starters For Future Codex Sessions

For future work, point Codex to the project skill at `skills/accessible-recipe-research/SKILL.md` first.

Useful prompts:

- "Use the project skill and add filtering by category in the sidebar."
- "Use the project skill and replace the placeholder transformation with a rule-based baseline."
- "Use the project skill and add exportable analytics for feedback events."
- "Use the project skill and evaluate whether the retrieval chunks are optimal for cooking questions."

## Security Notes

- Do not hardcode or print the OpenRouter API key.
- `.env` should remain local only.
- Runtime-generated files under `local_data/` should be treated as research artifacts, not committed source files.
