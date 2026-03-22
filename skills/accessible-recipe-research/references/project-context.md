# Project Context

## Goal

Convert sighted-oriented recipes into formats that work better for blind cooks, while preserving the original recipe, surfacing visual dependencies, and collecting user preference data for future model development.

## Current Architecture

- Sidebar search selects a recipe by title.
- Panel 1 renders the canonical recipe with VDD highlights and screen-reader-friendly structure.
- Panel 2 uses the same content for now, behind a transformation interface that can later swap to a real non-visual rewrite method.
- Panel 3 is a recipe-scoped chatbot using local chunking, OpenRouter embeddings, and OpenRouter chat completions.
- The chat panel uses Streamlit chat primitives for a text-only conversation thread.

## Source Of Truth

- Workbook: `Pilot Coding Worksheet Structure (v1.1).xlsx`
- Core sheets used now:
  - `Recipe_Metadata`
  - `Ingredients_List`
  - `Procedural_Text`
  - `Descriptor_Coding`

Important loader behavior:

- Some sheets contain an instructional/example row directly below the header.
- The loader skips those rows by validating `Recipe_ID` shape instead of assuming every row after the header is real data.

## Important Runtime Files

- Feedback log: `local_data/feedback_events.jsonl`
- Embedding cache: `local_data/embedding_cache.pkl`
- Sidebar analytics: `local_data/corpus_insights.json`
- Environment file: `.env`

## Known Limitations

- Panel 2 is still a placeholder and does not yet produce true non-visual rewrites.
- VDD phrase matching is heuristic. When an exact span cannot be located, the UI falls back to a sentence-level cue marker.
- There is no participant identity model yet beyond anonymous session ids.
- Retrieval uses in-memory cosine similarity rather than a vector database, which is acceptable for the current 200-recipe dataset.

## Stable Interfaces To Preserve

- `RecipeDocument`
- `DescriptorMatch`
- `TransformationService.transform(recipe)`
- `FeedbackLogger.log_preference(...)`
- `RecipeRAG.answer(recipe, question, chat_history)`

## Likely Next Tasks

- Add category filters and richer search.
- Add analytics views over preference events.
- Prototype a rule-based conversion baseline for Panel 2.
- Add evaluation scripts for VDD coverage and chatbot grounding quality.
- Compare different chunking or retrieval strategies for the chatbot.

## Prompt Suggestions

- "Use the project skill and implement a rule-based rewrite baseline for Panel 2 while preserving feedback logging."
- "Use the project skill and add an admin view that summarizes preference events by recipe and panel."
- "Use the project skill and evaluate whether descriptor fallback markers are too common, then improve matching."
- "Use the project skill and add tests for recipe chat retrieval without changing the public interface."
