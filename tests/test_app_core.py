from __future__ import annotations

import json
from pathlib import Path

from recipe_app.analytics import build_corpus_insights
from recipe_app.config import APP_VERSION
from recipe_app.data_loader import load_recipe_store
from recipe_app.feedback import FeedbackLogger
from recipe_app.highlighting import render_sentence_html
from recipe_app.transforms import TransformationService


WORKBOOK_PATH = Path(__file__).resolve().parent.parent / "Pilot Coding Worksheet Structure (v1.1).xlsx"


def test_loader_builds_all_200_recipes() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    assert len(store.recipes) == 200


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


def test_transformation_service_returns_placeholder_status() -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    transformed = TransformationService().transform(store.get("AP01"))
    assert transformed.status == "pending_conversion"
    assert transformed.note


def test_corpus_insights_are_written_to_file(tmp_path) -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    output_path = tmp_path / "corpus_insights.json"
    insights = build_corpus_insights(store, output_path=output_path)
    assert output_path.exists()
    assert "descriptor_code_counts" in insights
    assert "top_recipes_by_category" in insights
