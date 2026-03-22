from __future__ import annotations

import hashlib
import os
import pickle
from pathlib import Path

import numpy as np
import requests

from .config import (
    EMBEDDING_CACHE_PATH,
    MAX_CHAT_HISTORY_MESSAGES,
    OPENROUTER_API_BASE,
    OPENROUTER_CHAT_MODEL,
    OPENROUTER_EMBED_MODEL,
    OPENROUTER_TIMEOUT_SECONDS,
    RETRIEVAL_TOP_K,
)
from .models import RecipeDocument
from .supabase_store import SupabaseRecipeStore, SupabaseStoreError


class RecipeRAGError(RuntimeError):
    """Raised when the recipe chatbot cannot answer a question."""


class RecipeRAG:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        cache_path: str | Path = EMBEDDING_CACHE_PATH,
        chat_model: str = OPENROUTER_CHAT_MODEL,
        embedding_model: str = OPENROUTER_EMBED_MODEL,
        api_base: str = OPENROUTER_API_BASE,
        timeout_seconds: int = OPENROUTER_TIMEOUT_SECONDS,
        top_k: int = RETRIEVAL_TOP_K,
        max_history_messages: int = MAX_CHAT_HISTORY_MESSAGES,
        supabase_store: SupabaseRecipeStore | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.cache_path = Path(cache_path)
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.api_base = api_base.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.top_k = top_k
        self.max_history_messages = max_history_messages
        self.supabase_store = supabase_store
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._embedding_cache = self._load_cache()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def answer(
        self,
        recipe: RecipeDocument,
        question: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> str:
        if not self.api_key:
            raise RecipeRAGError(
                "The recipe chatbot is disabled until OPENROUTER_API_KEY is set in the environment."
            )

        retrieved_chunks = self._retrieve_relevant_chunks(recipe, question)
        context = "\n\n".join(
            f"{chunk_title}\n{chunk_text}" for chunk_title, chunk_text in retrieved_chunks
        )
        prompt = (
            f"Selected recipe: {recipe.title} ({recipe.category})\n"
            "Use only the grounded recipe context below. If the answer is not supported by the recipe, "
            "say that the current recipe does not contain enough information.\n\n"
            f"Grounded context:\n{context}\n\n"
            f"User question: {question}"
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an accessible cooking assistant for blind and low-vision cooks. "
                    "Answer with short, concrete guidance. Prefer step numbers, ingredient names, and "
                    "non-visual instructions when the recipe supports them. Do not invent missing details."
                ),
            }
        ]
        if chat_history:
            messages.extend(chat_history[-self.max_history_messages :])
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": 0.2,
        }
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RecipeRAGError(f"OpenRouter chat request failed: {exc}") from exc
        if response.status_code >= 400:
            raise RecipeRAGError(self._extract_error_message(response))
        body = response.json()
        try:
            return body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RecipeRAGError("OpenRouter returned an unexpected chat response.") from exc

    def _retrieve_relevant_chunks(self, recipe: RecipeDocument, question: str) -> list[tuple[str, str]]:
        query_embedding = np.asarray(self._embed_text(question), dtype=float)
        chunk_vectors: list[np.ndarray] = []
        chunk_texts: list[tuple[str, str]] = []

        remote_rows = None
        if self.supabase_store and self.supabase_store.is_configured():
            try:
                remote_rows = self.supabase_store.ensure_chunk_embeddings(
                    recipe,
                    embed_func=self._embed_text,
                    embedding_model=self.embedding_model,
                )
            except SupabaseStoreError:
                remote_rows = None

        if remote_rows is not None:
            for row in remote_rows:
                chunk_vectors.append(np.asarray(row["embedding"], dtype=float))
                chunk_texts.append((str(row["title"]), str(row["text"])))
        else:
            for chunk in recipe.chunks:
                chunk_vectors.append(np.asarray(self._get_or_create_embedding(chunk.chunk_id, chunk.text), dtype=float))
                chunk_texts.append((chunk.title, chunk.text))

        if not chunk_vectors:
            return [("Recipe context", recipe.chatbot_context)]

        matrix = np.vstack(chunk_vectors)
        norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_embedding)
        scores = np.divide(
            matrix @ query_embedding,
            norms,
            out=np.zeros_like(norms),
            where=norms != 0,
        )
        top_indices = np.argsort(scores)[::-1][: min(self.top_k, len(chunk_texts))]
        return [chunk_texts[index] for index in top_indices]

    def _get_or_create_embedding(self, chunk_id: str, text: str) -> list[float]:
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cached = self._embedding_cache.get(chunk_id)
        if cached and cached.get("text_hash") == text_hash and cached.get("model") == self.embedding_model:
            return cached["embedding"]

        embedding = self._embed_text(text)
        self._embedding_cache[chunk_id] = {
            "text_hash": text_hash,
            "model": self.embedding_model,
            "embedding": embedding,
        }
        self._save_cache()
        return embedding

    def _embed_text(self, text: str) -> list[float]:
        payload = {
            "model": self.embedding_model,
            "input": text,
        }
        try:
            response = requests.post(
                f"{self.api_base}/embeddings",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RecipeRAGError(f"OpenRouter embeddings request failed: {exc}") from exc
        if response.status_code >= 400:
            raise RecipeRAGError(self._extract_error_message(response))
        body = response.json()
        try:
            return body["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RecipeRAGError("OpenRouter returned an unexpected embeddings response.") from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": "Accessible Recipe Prototype",
        }

    def _load_cache(self) -> dict[str, dict[str, object]]:
        if not self.cache_path.exists():
            return {}
        try:
            with self.cache_path.open("rb") as handle:
                cache = pickle.load(handle)
        except Exception:
            return {}
        return cache if isinstance(cache, dict) else {}

    def _save_cache(self) -> None:
        with self.cache_path.open("wb") as handle:
            pickle.dump(self._embedding_cache, handle)

    @staticmethod
    def _extract_error_message(response: requests.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            body = {}
        detail = body.get("error", {}).get("message") or body.get("message")
        if detail:
            return str(detail)
        return f"OpenRouter request failed with status {response.status_code}."
