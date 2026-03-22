from __future__ import annotations

import json
from pathlib import Path

import requests

from app import _build_export_payload
from recipe_app.analytics import build_corpus_insights
from recipe_app.config import APP_VERSION
from recipe_app.data_loader import build_recipe_document, load_recipe_store
from recipe_app.feedback import FeedbackLogger
from recipe_app.highlighting import render_sentence_html
from recipe_app.rag import RecipeRAG, RecipeRAGError
from recipe_app.supabase_store import SupabaseRecipeStore, SupabaseStoreError
from recipe_app.transforms import TransformationService


WORKBOOK_PATH = Path(__file__).resolve().parent.parent / "Pilot Coding Worksheet Structure (v1.1).xlsx"


def test_loader_builds_all_200_recipes() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    assert len(store.recipes) == 200


def test_loader_defaults_version_two_to_version_one_when_workbook_has_no_version_two_columns() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    recipe = store.get("AP01")
    assert recipe.version_two_ingredients == recipe.ingredients
    assert recipe.version_two_steps == recipe.steps


def test_search_matches_recipe_title_case_insensitively() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    matches = store.search("chicken piccata")
    assert matches
    assert matches[0].title == "Chicken Piccata"


def test_filter_matches_recipe_id_category_rating_and_descriptor_code() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    matches = store.filter_recipes(
        recipe_id_query="AP01",
        categories=["Appetizer"],
        rating_range=(0.0, 5.0),
        descriptor_codes=["COLOR_BROWNING"],
    )
    assert matches
    assert matches[0].recipe_id == "AP01"


def test_exact_vdd_phrase_is_highlighted() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    recipe = store.get("AP01")
    target_sentence = next(
        sentence
        for step in recipe.steps
        for sentence in step.sentences
        if sentence.step_number == 4 and sentence.sentence_number == 4
    )
    html = render_sentence_html(target_sentence)
    assert "vdd-highlight" in html
    assert "bubbly" in html


def test_non_exact_vdd_phrase_falls_back_to_sentence_marker() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    recipe = store.get("DE02")
    target_sentence = next(
        sentence
        for step in recipe.steps
        for sentence in step.sentences
        if sentence.step_number == 5 and sentence.sentence_number == 1
    )
    assert any(descriptor.match_type == "sentence" for descriptor in target_sentence.descriptors)
    html = render_sentence_html(target_sentence)
    assert "vdd-fallback-marker" in html


def test_duplicate_procedural_rows_are_deduplicated() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    recipe = store.get("BR02")
    step_one_texts = [sentence.text for sentence in recipe.steps[0].sentences]
    assert step_one_texts == [
        "Preheat the oven to 375 degrees F.",
        "Line a sheet pan with parchment paper.",
    ]


def test_feedback_logger_appends_jsonl_records(tmp_path) -> None:
    logger = FeedbackLogger(path=tmp_path / "feedback.jsonl")
    logger.log_preference(
        session_id="session-1",
        recipe_id="AP01",
        panel_id="panel_1",
        content_version="canonical_v1",
    )
    logger.log_preference(
        session_id="session-1",
        recipe_id="AP01",
        panel_id="panel_2",
        content_version="placeholder_conversion_v1",
    )

    lines = (tmp_path / "feedback.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    payload = json.loads(lines[0])
    assert payload["session_id"] == "session-1"
    assert payload["app_version"] == APP_VERSION


def test_feedback_logger_prefers_supabase_when_configured(tmp_path, monkeypatch) -> None:
    store = SupabaseRecipeStore(
        url="https://example.supabase.co",
        api_key="test-key",
        rest_url="https://example.supabase.co/rest/v1",
    )
    inserted: list[object] = []

    def fake_insert(event) -> None:
        inserted.append(event)

    monkeypatch.setattr(store, "insert_feedback_event", fake_insert)
    logger = FeedbackLogger(path=tmp_path / "feedback.jsonl", supabase_store=store)

    logger.log_preference(
        session_id="session-1",
        recipe_id="AP01",
        panel_id="panel_1",
        content_version="canonical_v1",
    )

    assert len(inserted) == 1
    assert not (tmp_path / "feedback.jsonl").exists()


def test_feedback_logger_falls_back_to_local_when_supabase_insert_fails(tmp_path, monkeypatch) -> None:
    store = SupabaseRecipeStore(
        url="https://example.supabase.co",
        api_key="test-key",
        rest_url="https://example.supabase.co/rest/v1",
    )

    def fake_insert(event) -> None:
        raise SupabaseStoreError("insert failed")

    monkeypatch.setattr(store, "insert_feedback_event", fake_insert)
    logger = FeedbackLogger(path=tmp_path / "feedback.jsonl", supabase_store=store)

    logger.log_preference(
        session_id="session-1",
        recipe_id="AP01",
        panel_id="panel_1",
        content_version="canonical_v1",
    )

    lines = (tmp_path / "feedback.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert logger.last_warning == "insert failed"


def test_transformation_service_returns_placeholder_status() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    transformed = TransformationService().transform(store.get("AP01"))
    assert transformed.status == "pending_conversion"
    assert transformed.note


def test_build_recipe_document_creates_manual_recipe() -> None:
    recipe = build_recipe_document(
        recipe_id="ZZ99",
        title="Test Recipe",
        category="Custom",
        url="https://example.com/recipe",
        star_rating=4.5,
        review_count=12,
        ingredient_lines=["1 cup flour", "1 cup water"],
        step_lines=["Mix ingredients.", "Bake until done."],
    )

    assert recipe.recipe_id == "ZZ99"
    assert len(recipe.ingredients) == 2
    assert len(recipe.steps) == 2
    assert recipe.steps[0].sentences[0].text == "Mix ingredients."
    assert recipe.descriptor_count == 0
    assert recipe.chunks[0].chunk_id == "ZZ99:overview"
    assert recipe.version_two_ingredients == recipe.ingredients
    assert recipe.version_two_steps == recipe.steps


def test_export_payload_includes_votes_and_both_versions() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    supabase_store = SupabaseRecipeStore(
        url="https://example.supabase.co",
        api_key="test-key",
        rest_url="https://example.supabase.co/rest/v1",
    )
    payload = json.loads(
        _build_export_payload(
            store,
            supabase_store,
            TransformationService(),
        )
    )

    assert payload["recipe_count"] == 200
    first_recipe = payload["recipes"][0]
    assert "version_1" in first_recipe["versions"]
    assert "version_2" in first_recipe["versions"]
    assert "votes" in first_recipe
    assert set(first_recipe["votes"]) == {"version_1", "version_2"}


def test_rag_wraps_embedding_request_timeouts(monkeypatch) -> None:
    rag = RecipeRAG(api_key="test-key")

    def fake_post(*args, **kwargs):
        raise requests.ReadTimeout("timed out")

    monkeypatch.setattr(requests, "post", fake_post)

    try:
        rag._embed_text("test text")
    except RecipeRAGError as exc:
        assert "OpenRouter embeddings request failed" in str(exc)
    else:
        raise AssertionError("RecipeRAGError was not raised for embedding timeout")


def test_rag_wraps_chat_request_timeouts(monkeypatch) -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    recipe = store.get("AP01")
    rag = RecipeRAG(api_key="test-key")

    monkeypatch.setattr(
        rag,
        "_retrieve_relevant_chunks",
        lambda recipe, question: [("Recipe overview", "Grounded test context")],
    )

    def fake_post(*args, **kwargs):
        raise requests.ReadTimeout("timed out")

    monkeypatch.setattr(requests, "post", fake_post)

    try:
        rag.answer(recipe, "What do I do first?")
    except RecipeRAGError as exc:
        assert "OpenRouter chat request failed" in str(exc)
    else:
        raise AssertionError("RecipeRAGError was not raised for chat timeout")


def test_corpus_insights_are_written_to_file(tmp_path) -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    output_path = tmp_path / "corpus_insights.json"
    insights = build_corpus_insights(store, output_path=output_path)
    assert output_path.exists()
    assert "descriptor_code_counts" in insights
    assert "top_recipes_by_category" in insights
