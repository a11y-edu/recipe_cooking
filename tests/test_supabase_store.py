from __future__ import annotations

from pathlib import Path

from recipe_app.data_loader import build_recipe_document, load_recipe_store
from recipe_app.supabase_store import SupabaseRecipeStore


WORKBOOK_PATH = Path(__file__).resolve().parent.parent / "Pilot Coding Worksheet Structure (v1.1).xlsx"


def test_recipe_record_roundtrip() -> None:
    recipe = build_recipe_document(
        recipe_id="ZZ98",
        title="Roundtrip Recipe",
        category="Custom",
        ingredient_lines=["1 apple"],
        step_lines=["Slice the apple."],
        version_two_ingredient_lines=["1 peeled apple"],
        version_two_step_lines=["Peel and slice the apple."],
    )
    record = SupabaseRecipeStore._recipe_to_record(recipe)
    rebuilt = SupabaseRecipeStore._recipe_from_record(record)

    assert rebuilt.recipe_id == recipe.recipe_id
    assert rebuilt.title == recipe.title
    assert rebuilt.category == recipe.category
    assert len(rebuilt.ingredients) == len(recipe.ingredients)
    assert len(rebuilt.steps) == len(recipe.steps)
    assert rebuilt.descriptor_count == recipe.descriptor_count
    assert rebuilt.chunks[0].chunk_id == recipe.chunks[0].chunk_id
    assert rebuilt.version_two_ingredients[0].full_text == "1 peeled apple"
    assert rebuilt.version_two_steps[0].sentences[0].text == "Peel and slice the apple."


def test_load_or_sync_recipe_store_uses_remote_rows_without_workbook(monkeypatch) -> None:
    store = load_recipe_store(WORKBOOK_PATH)
    remote_record = SupabaseRecipeStore._recipe_to_record(store.get("AP01"))
    supabase_store = SupabaseRecipeStore(
        url="https://example.supabase.co",
        api_key="test-key",
        rest_url="https://example.supabase.co/rest/v1",
    )

    monkeypatch.setattr(supabase_store, "_fetch_recipes", lambda: [remote_record])
    monkeypatch.setattr(
        supabase_store,
        "upsert_recipes",
        lambda recipes: (_ for _ in ()).throw(AssertionError("upsert should not be called")),
    )

    result = supabase_store.load_or_sync_recipe_store(None)

    assert list(result.recipes) == ["AP01"]
    assert result.get("AP01").title == store.get("AP01").title
    assert result.workbook_path == Path("supabase")


def test_load_or_sync_recipe_store_seeds_remote_when_empty(monkeypatch) -> None:
    fallback_store = load_recipe_store(WORKBOOK_PATH)
    supabase_store = SupabaseRecipeStore(
        url="https://example.supabase.co",
        api_key="test-key",
        rest_url="https://example.supabase.co/rest/v1",
    )

    remote_rows: list[dict[str, object]] = []
    upserted_ids: list[str] = []

    def fake_fetch_recipes() -> list[dict[str, object]]:
        return list(remote_rows)

    def fake_upsert(recipes) -> None:
        upserted_ids.extend(recipe.recipe_id for recipe in recipes)
        remote_rows[:] = [SupabaseRecipeStore._recipe_to_record(recipe) for recipe in recipes]

    monkeypatch.setattr(supabase_store, "_fetch_recipes", fake_fetch_recipes)
    monkeypatch.setattr(supabase_store, "upsert_recipes", fake_upsert)

    result = supabase_store.load_or_sync_recipe_store(fallback_store)

    assert len(upserted_ids) == len(fallback_store.recipes)
    assert len(result.recipes) == len(fallback_store.recipes)
    assert result.get("AP01").title == fallback_store.get("AP01").title


def test_load_or_sync_recipe_store_does_not_reseed_when_remote_has_extra_recipe(monkeypatch) -> None:
    fallback_store = load_recipe_store(WORKBOOK_PATH)
    supabase_store = SupabaseRecipeStore(
        url="https://example.supabase.co",
        api_key="test-key",
        rest_url="https://example.supabase.co/rest/v1",
    )

    remote_rows = [SupabaseRecipeStore._recipe_to_record(recipe) for recipe in fallback_store.list_recipes()]
    remote_rows.append(
        {
            **SupabaseRecipeStore._recipe_to_record(fallback_store.get("AP01")),
            "recipe_id": "ZZ99",
            "title": "Extra Recipe",
        }
    )

    monkeypatch.setattr(supabase_store, "_fetch_recipes", lambda: list(remote_rows))
    monkeypatch.setattr(
        supabase_store,
        "upsert_recipes",
        lambda recipes: (_ for _ in ()).throw(AssertionError("upsert should not be called")),
    )

    result = supabase_store.load_or_sync_recipe_store(fallback_store)

    assert "ZZ99" in result.recipes
    assert len(result.recipes) == len(fallback_store.recipes) + 1


def test_reset_recipes_from_store_deletes_then_reloads(monkeypatch) -> None:
    fallback_store = load_recipe_store(WORKBOOK_PATH)
    supabase_store = SupabaseRecipeStore(
        url="https://example.supabase.co",
        api_key="test-key",
        rest_url="https://example.supabase.co/rest/v1",
    )
    deleted: list[tuple[str, str]] = []
    upserted: list[str] = []

    monkeypatch.setattr(
        supabase_store,
        "_delete_all_rows",
        lambda table, identity_column: deleted.append((table, identity_column)),
    )
    monkeypatch.setattr(
        supabase_store,
        "upsert_recipes",
        lambda recipes: upserted.extend(recipe.recipe_id for recipe in recipes),
    )
    monkeypatch.setattr(supabase_store, "load_or_sync_recipe_store", lambda store: store)

    result = supabase_store.reset_recipes_from_store(fallback_store)

    assert deleted == [("recipes", "recipe_id")]
    assert len(upserted) == len(fallback_store.recipes)
    assert result is fallback_store
