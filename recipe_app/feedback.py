from __future__ import annotations

import json
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .config import APP_VERSION, FEEDBACK_PATH
from .models import FeedbackEvent
from .supabase_store import SupabaseRecipeStore, SupabaseStoreError


class FeedbackLogger:
    def __init__(
        self,
        path: str | Path = FEEDBACK_PATH,
        *,
        app_version: str = APP_VERSION,
        supabase_store: SupabaseRecipeStore | None = None,
    ) -> None:
        self.path = Path(path)
        self.app_version = app_version
        self.supabase_store = supabase_store
        self.last_warning: str | None = None
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_preference(
        self,
        *,
        session_id: str,
        recipe_id: str,
        panel_id: str,
        content_version: str,
    ) -> FeedbackEvent:
        event = FeedbackEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            recipe_id=recipe_id,
            panel_id=panel_id,
            content_version=content_version,
            app_version=self.app_version,
        )
        if self.supabase_store and self.supabase_store.is_configured():
            try:
                self.supabase_store.insert_feedback_event(event)
                self.last_warning = None
                return event
            except SupabaseStoreError as exc:
                self.last_warning = str(exc)

        payload = json.dumps(asdict(event), ensure_ascii=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(payload + "\n")
        return event
