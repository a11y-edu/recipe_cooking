from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_VERSION = "0.2.0"
APP_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKBOOK_PATH = APP_ROOT / "Pilot Coding Worksheet Structure (v1.1).xlsx"
WORKBOOK_PATH = Path(os.getenv("RECIPE_WORKBOOK_PATH", str(DEFAULT_WORKBOOK_PATH)))

LOCAL_DATA_DIR = APP_ROOT / "local_data"
FEEDBACK_PATH = LOCAL_DATA_DIR / "feedback_events.jsonl"
EMBEDDING_CACHE_PATH = LOCAL_DATA_DIR / "embedding_cache.pkl"
CORPUS_INSIGHTS_PATH = LOCAL_DATA_DIR / "corpus_insights.json"

OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_MODEL = os.getenv(
    "OPENROUTER_CHAT_MODEL",
    "nvidia/nemotron-3-super-120b-a12b:free",
)
OPENROUTER_EMBED_MODEL = os.getenv(
    "OPENROUTER_EMBED_MODEL",
    "nvidia/llama-nemotron-embed-vl-1b-v2:free",
)
OPENROUTER_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "45"))

RETRIEVAL_TOP_K = int(os.getenv("RECIPE_RAG_TOP_K", "4"))
MAX_CHAT_HISTORY_MESSAGES = int(os.getenv("RECIPE_CHAT_HISTORY_MESSAGES", "6"))

PANEL_ONE_VERSION = "canonical_v1"
PANEL_TWO_VERSION = "placeholder_conversion_v1"

CATEGORY_COLORS = {
    "COLOR_BROWNING": "#B65B3A",
    "COLOR_TRANSLUCENT": "#4E8F98",
    "COLOR_SHINY": "#7661A8",
    "COLOR_DONENESS_RAW": "#B04A69",
    "COLOR_BRIGHT_GREEN": "#407B3A",
    "SURFACE_BUBBLY": "#B8842C",
    "OTHER_VDD": "#5D6A79",
}

CATEGORY_LABELS = {
    "COLOR_BROWNING": "Browning cue",
    "COLOR_TRANSLUCENT": "Transparency cue",
    "COLOR_SHINY": "Shine cue",
    "COLOR_DONENESS_RAW": "Rawness cue",
    "COLOR_BRIGHT_GREEN": "Bright green cue",
    "SURFACE_BUBBLY": "Bubble cue",
    "OTHER_VDD": "Other visual cue",
}
