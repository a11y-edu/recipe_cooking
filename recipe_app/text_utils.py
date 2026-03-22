from __future__ import annotations

import re
import unicodedata

RECIPE_ID_PATTERN = re.compile(r"^[A-Z]{2,4}\d{2,}$")

QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u00a0": " ",
    }
)


def looks_like_recipe_id(value: object) -> bool:
    return isinstance(value, str) and bool(RECIPE_ID_PATTERN.match(value.strip()))


def normalize_quotes(text: str) -> str:
    return text.translate(QUOTE_TRANSLATION)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def safe_text(value: object) -> str:
    if value is None:
        return ""
    return normalize_whitespace(str(value))


def to_int(value: object, default: int = 0) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return int(float(str(value).strip()))


def to_optional_text(value: object) -> str | None:
    text = safe_text(value)
    return text or None


def to_bool_flag(value: object) -> bool | None:
    text = safe_text(value).casefold()
    if not text:
        return None
    if text in {"yes", "true", "1"}:
        return True
    if text in {"no", "false", "0"}:
        return False
    return None


def build_indexed_view(
    text: str,
    *,
    keep_char: callable | None = None,
) -> tuple[str, list[int]]:
    normalized = normalize_quotes(text)
    chars: list[str] = []
    index_map: list[int] = []
    for original_index, char in enumerate(normalized):
        for folded in unicodedata.normalize("NFKC", char).casefold():
            if keep_char is not None and not keep_char(folded):
                continue
            chars.append(folded)
            index_map.append(original_index)
    return "".join(chars), index_map


def strip_outer_quotes(text: str) -> str:
    stripped = normalize_whitespace(normalize_quotes(text))
    return stripped.strip("\"'")
