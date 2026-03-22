from __future__ import annotations

import hashlib
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Callable

import requests

from .config import (
    OPENROUTER_EMBED_MODEL,
    OPENROUTER_TIMEOUT_SECONDS,
    SUPABASE_API_KEY,
    SUPABASE_REST_URL,
    SUPABASE_URL,
)
from .data_loader import RecipeStore
from .models import (
    DescriptorMatch,
    FeedbackEvent,
    IngredientLine,
    RecipeChunk,
    RecipeDocument,
    RecipeSentence,
    RecipeStep,
)


class SupabaseStoreError(RuntimeError):
    """Raised when the app cannot use the configured Supabase backend."""


class SupabaseRecipeStore:
    def __init__(
        self,
        *,
        url: str = SUPABASE_URL,
        api_key: str = SUPABASE_API_KEY,
        rest_url: str = SUPABASE_REST_URL,
        timeout_seconds: int = OPENROUTER_TIMEOUT_SECONDS,
        embedding_model: str = OPENROUTER_EMBED_MODEL,
    ) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.rest_url = rest_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.embedding_model = embedding_model
        self.last_warning: str | None = None

    def is_configured(self) -> bool:
        return bool(self.url and self.api_key and self.rest_url)

    def load_or_sync_recipe_store(self, fallback_store: RecipeStore | None = None) -> RecipeStore:
        if not self.is_configured():
            if fallback_store is not None:
                return fallback_store
            raise SupabaseStoreError(
                "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY, "
                "or use the legacy SUPABASE_SERVICE_ROLE_KEY, or SUPABASE_ANON_KEY."
            )
        try:
            remote_rows = self._fetch_recipes()
            if not remote_rows and fallback_store is not None:
                self.upsert_recipes(fallback_store.list_recipes())
                remote_rows = self._fetch_recipes()
            elif fallback_store is not None:
                remote_ids = {str(row.get("recipe_id") or "") for row in remote_rows}
                local_ids = set(fallback_store.recipes)
                if not local_ids.issubset(remote_ids):
                    self.upsert_recipes(fallback_store.list_recipes())
                    remote_rows = self._fetch_recipes()
            recipes = {
                recipe.recipe_id: self._merge_with_fallback_version_two(recipe, fallback_store)
                for recipe in (self._recipe_from_record(row) for row in remote_rows)
            }
            if recipes:
                self.last_warning = None
                store_path = fallback_store.workbook_path if fallback_store is not None else Path("supabase")
                return RecipeStore(workbook_path=store_path, recipes=recipes)
        except SupabaseStoreError as exc:
            self.last_warning = str(exc)
        if fallback_store is not None:
            return fallback_store
        raise SupabaseStoreError(self.last_warning or "Supabase could not load recipes.")

    def upsert_recipes(self, recipes: list[RecipeDocument]) -> None:
        payload = [self._recipe_to_record(recipe) for recipe in recipes]
        self._upsert_recipe_payload(payload)

    def upsert_recipe(self, recipe: RecipeDocument) -> None:
        self.upsert_recipes([recipe])

    def export_recipe_records(self) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise SupabaseStoreError("Supabase is not configured.")
        return self._fetch_recipes()

    def get_feedback_vote_counts(self) -> dict[str, dict[str, int]]:
        if not self.is_configured():
            return {}
        try:
            rows = self._request(
                "GET",
                "feedback_events",
                params={"select": "recipe_id,panel_id"},
            )
        except SupabaseStoreError:
            return {}
        counts: dict[str, dict[str, int]] = {}
        for row in rows if isinstance(rows, list) else []:
            recipe_id = str(row.get("recipe_id") or "")
            panel_id = str(row.get("panel_id") or "")
            if not recipe_id or not panel_id:
                continue
            recipe_counts = counts.setdefault(recipe_id, {"panel_1": 0, "panel_2": 0})
            recipe_counts[panel_id] = recipe_counts.get(panel_id, 0) + 1
        return counts

    def reset_recipes_from_store(self, fallback_store: RecipeStore) -> RecipeStore:
        if not self.is_configured():
            raise SupabaseStoreError("Supabase is not configured.")
        self._delete_all_rows("recipes", "recipe_id")
        self.upsert_recipes(fallback_store.list_recipes())
        self.last_warning = None
        return self.load_or_sync_recipe_store(fallback_store)

    def ensure_chunk_embeddings(
        self,
        recipe: RecipeDocument,
        *,
        embed_func: Callable[[str], list[float]],
        embedding_model: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise SupabaseStoreError("Supabase is not configured.")
        embedding_model = embedding_model or self.embedding_model
        existing_rows = self._fetch_chunk_rows(recipe.recipe_id)
        existing_by_chunk_id = {row["chunk_id"]: row for row in existing_rows}
        resolved_rows: list[dict[str, Any]] = []
        upsert_rows: list[dict[str, Any]] = []

        for chunk in recipe.chunks:
            text_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            existing_row = existing_by_chunk_id.get(chunk.chunk_id)
            if (
                existing_row
                and existing_row.get("text_hash") == text_hash
                and existing_row.get("embedding_model") == embedding_model
                and existing_row.get("embedding")
            ):
                resolved_rows.append(existing_row)
                continue

            row = {
                "chunk_id": chunk.chunk_id,
                "recipe_id": recipe.recipe_id,
                "title": chunk.title,
                "text": chunk.text,
                "text_hash": text_hash,
                "embedding_model": embedding_model,
                "embedding": embed_func(chunk.text),
            }
            upsert_rows.append(row)
            resolved_rows.append(row)

        if upsert_rows:
            self._request(
                "POST",
                "recipe_chunks",
                params={"on_conflict": "chunk_id"},
                json_body=upsert_rows,
                prefer="resolution=merge-duplicates",
            )
        return resolved_rows

    def insert_feedback_event(self, event: FeedbackEvent) -> None:
        if not self.is_configured():
            raise SupabaseStoreError("Supabase is not configured.")
        self._request(
            "POST",
            "feedback_events",
            json_body={
                "timestamp": event.timestamp,
                "session_id": event.session_id,
                "recipe_id": event.recipe_id,
                "panel_id": event.panel_id,
                "content_version": event.content_version,
                "app_version": event.app_version,
            },
        )

    def _fetch_recipes(self) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "recipes",
            params={
                "select": "*",
                "order": "recipe_id.asc",
            },
        )
        return response if isinstance(response, list) else []

    def _fetch_chunk_rows(self, recipe_id: str) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "recipe_chunks",
            params={
                "select": "chunk_id,recipe_id,title,text,text_hash,embedding_model,embedding",
                "recipe_id": f"eq.{recipe_id}",
                "order": "chunk_id.asc",
            },
        )
        return response if isinstance(response, list) else []

    def _request(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = requests.request(
                method=method,
                url=f"{self.rest_url}/{table}",
                headers=headers,
                params=params,
                json=json_body,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise SupabaseStoreError(str(exc)) from exc
        if response.status_code >= 400:
            raise SupabaseStoreError(self._extract_error_message(response))
        if not response.text:
            return None
        return response.json()

    def _delete_all_rows(self, table: str, identity_column: str) -> None:
        self._request(
            "DELETE",
            table,
            params={identity_column: "not.is.null"},
        )

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            body = {}
        detail = body.get("message") or body.get("error") or body.get("hint")
        if detail:
            return str(detail)
        return f"Supabase request failed with status {response.status_code}."

    @staticmethod
    def _recipe_to_record(recipe: RecipeDocument) -> dict[str, Any]:
        return {
            "recipe_id": recipe.recipe_id,
            "title": recipe.title,
            "category": recipe.category,
            "url": recipe.url,
            "star_rating": recipe.star_rating,
            "review_count": recipe.review_count,
            "ingredients": [asdict(item) for item in recipe.ingredients],
            "steps": [asdict(step) for step in recipe.steps],
            "descriptors": [asdict(item) for item in recipe.descriptors],
            "descriptor_count": recipe.descriptor_count,
            "descriptor_code_counts": recipe.descriptor_code_counts,
            "chatbot_context": recipe.chatbot_context,
            "chunks": [asdict(chunk) for chunk in recipe.chunks],
            "version_2_ingredients": [asdict(item) for item in recipe.version_two_ingredients],
            "version_2_steps": [asdict(step) for step in recipe.version_two_steps],
        }

    @staticmethod
    def _recipe_from_record(record: dict[str, Any]) -> RecipeDocument:
        ingredients = [
            IngredientLine(**item)
            for item in (record.get("ingredients") or [])
        ]
        descriptors = [
            DescriptorMatch(**item)
            for item in (record.get("descriptors") or [])
        ]

        steps: list[RecipeStep] = []
        for step_payload in record.get("steps") or []:
            sentences: list[RecipeSentence] = []
            for sentence_payload in step_payload.get("sentences") or []:
                sentence_descriptors = [
                    DescriptorMatch(**item)
                    for item in (sentence_payload.get("descriptors") or [])
                ]
                sentences.append(
                    RecipeSentence(
                        step_number=int(sentence_payload["step_number"]),
                        sentence_number=int(sentence_payload["sentence_number"]),
                        text=str(sentence_payload["text"]),
                        descriptors=sentence_descriptors,
                    )
                )
            steps.append(
                RecipeStep(
                    step_number=int(step_payload["step_number"]),
                    sentences=sentences,
                )
            )

        chunks = [
            RecipeChunk(**item)
            for item in (record.get("chunks") or [])
        ]
        descriptor_code_counts = {
            str(key): int(value)
            for key, value in (record.get("descriptor_code_counts") or {}).items()
        }
        version_two_ingredients = [
            IngredientLine(**item)
            for item in (record.get("version_2_ingredients") or [])
        ]
        version_two_steps: list[RecipeStep] = []
        for step_payload in record.get("version_2_steps") or []:
            sentences = [
                RecipeSentence(
                    step_number=int(sentence_payload["step_number"]),
                    sentence_number=int(sentence_payload["sentence_number"]),
                    text=str(sentence_payload["text"]),
                    descriptors=[],
                )
                for sentence_payload in (step_payload.get("sentences") or [])
            ]
            version_two_steps.append(
                RecipeStep(
                    step_number=int(step_payload["step_number"]),
                    sentences=sentences,
                )
            )
        return RecipeDocument(
            recipe_id=str(record["recipe_id"]),
            title=str(record["title"]),
            category=str(record["category"]),
            url=str(record.get("url") or ""),
            star_rating=float(record["star_rating"]) if record.get("star_rating") is not None else None,
            review_count=int(record["review_count"]) if record.get("review_count") is not None else None,
            ingredients=ingredients,
            steps=steps,
            descriptors=descriptors,
            descriptor_count=int(record.get("descriptor_count") or len(descriptors)),
            descriptor_code_counts=descriptor_code_counts,
            chatbot_context=str(record.get("chatbot_context") or ""),
            chunks=chunks,
            version_two_ingredients=version_two_ingredients or ingredients,
            version_two_steps=version_two_steps or steps,
        )

    def _upsert_recipe_payload(self, payload: list[dict[str, Any]]) -> None:
        try:
            for batch_start in range(0, len(payload), 25):
                batch = payload[batch_start : batch_start + 25]
                self._request(
                    "POST",
                    "recipes",
                    params={"on_conflict": "recipe_id"},
                    json_body=batch,
                    prefer="resolution=merge-duplicates",
                )
        except SupabaseStoreError as exc:
            if "version_2_" not in str(exc):
                raise
            stripped_payload = [
                {
                    key: value
                    for key, value in record.items()
                    if key not in {"version_2_ingredients", "version_2_steps"}
                }
                for record in payload
            ]
            for batch_start in range(0, len(stripped_payload), 25):
                batch = stripped_payload[batch_start : batch_start + 25]
                self._request(
                    "POST",
                    "recipes",
                    params={"on_conflict": "recipe_id"},
                    json_body=batch,
                    prefer="resolution=merge-duplicates",
                )

    @staticmethod
    def _merge_with_fallback_version_two(
        remote_recipe: RecipeDocument,
        fallback_store: RecipeStore | None,
    ) -> RecipeDocument:
        if fallback_store is None or remote_recipe.recipe_id not in fallback_store.recipes:
            return remote_recipe
        fallback_recipe = fallback_store.get(remote_recipe.recipe_id)
        remote_has_distinct_version_two = (
            remote_recipe.version_two_ingredients != remote_recipe.ingredients
            or remote_recipe.version_two_steps != remote_recipe.steps
        )
        fallback_has_distinct_version_two = (
            fallback_recipe.version_two_ingredients != fallback_recipe.ingredients
            or fallback_recipe.version_two_steps != fallback_recipe.steps
        )
        if remote_has_distinct_version_two or not fallback_has_distinct_version_two:
            return remote_recipe
        return replace(
            remote_recipe,
            version_two_ingredients=fallback_recipe.version_two_ingredients,
            version_two_steps=fallback_recipe.version_two_steps,
        )
