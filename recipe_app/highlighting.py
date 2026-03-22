from __future__ import annotations

from dataclasses import replace
from html import escape
from typing import Iterable

from .config import CATEGORY_COLORS, CATEGORY_LABELS
from .models import DescriptorMatch, RecipeSentence
from .text_utils import build_indexed_view, normalize_whitespace, strip_outer_quotes


def _find_non_overlapping(
    sentence_text: str,
    descriptor_text: str,
    occupied_ranges: list[tuple[int, int]],
    *,
    keep_char: callable | None = None,
) -> tuple[int, int] | None:
    sentence_view, sentence_map = build_indexed_view(sentence_text, keep_char=keep_char)
    descriptor_view, _ = build_indexed_view(descriptor_text, keep_char=keep_char)
    descriptor_view = normalize_whitespace(descriptor_view)
    if not descriptor_view:
        return None

    search_from = 0
    while True:
        start_in_view = sentence_view.find(descriptor_view, search_from)
        if start_in_view == -1:
            return None
        end_in_view = start_in_view + len(descriptor_view)
        start = sentence_map[start_in_view]
        end = sentence_map[end_in_view - 1] + 1
        if all(end <= taken_start or start >= taken_end for taken_start, taken_end in occupied_ranges):
            return start, end
        search_from = start_in_view + 1


def locate_descriptor_span(
    sentence_text: str,
    descriptor_text: str,
    occupied_ranges: list[tuple[int, int]],
) -> tuple[int, int] | None:
    descriptor_variants = []
    base = normalize_whitespace(descriptor_text)
    if base:
        descriptor_variants.append(base)

    stripped = strip_outer_quotes(descriptor_text)
    if stripped and stripped not in descriptor_variants:
        descriptor_variants.append(stripped)

    keep_all = None
    keep_without_quotes = lambda ch: ch not in {'"', "'"}  # noqa: E731
    keep_words_and_spaces = lambda ch: ch.isalnum() or ch.isspace()  # noqa: E731

    for variant in descriptor_variants:
        for keep_char in (keep_all, keep_without_quotes, keep_words_and_spaces):
            match = _find_non_overlapping(
                sentence_text,
                variant,
                occupied_ranges,
                keep_char=keep_char,
            )
            if match:
                return match
    return None


def resolve_sentence_descriptors(
    sentence_text: str,
    descriptors: Iterable[DescriptorMatch],
) -> list[DescriptorMatch]:
    occupied_ranges: list[tuple[int, int]] = []
    resolved: list[DescriptorMatch] = []
    for descriptor in descriptors:
        span = locate_descriptor_span(sentence_text, descriptor.descriptor_text, occupied_ranges)
        if span:
            occupied_ranges.append(span)
            resolved.append(
                replace(
                    descriptor,
                    span_start=span[0],
                    span_end=span[1],
                    match_type="span",
                )
            )
            continue
        resolved.append(replace(descriptor, match_type="sentence"))
    return resolved


def render_sentence_html(sentence: RecipeSentence) -> str:
    text = sentence.text
    span_descriptors = [
        descriptor
        for descriptor in sentence.descriptors
        if descriptor.match_type == "span"
        and descriptor.span_start is not None
        and descriptor.span_end is not None
    ]
    span_descriptors.sort(key=lambda descriptor: (descriptor.span_start, descriptor.span_end))

    parts: list[str] = []
    cursor = 0
    fallback_descriptors: list[DescriptorMatch] = []
    for descriptor in span_descriptors:
        start = descriptor.span_start or 0
        end = descriptor.span_end or 0
        if start < cursor:
            fallback_descriptors.append(replace(descriptor, match_type="sentence", span_start=None, span_end=None))
            continue
        parts.append(escape(text[cursor:start]))
        parts.append(_highlight_span_html(text[start:end], descriptor))
        cursor = end
    parts.append(escape(text[cursor:]))

    for descriptor in sentence.descriptors:
        if descriptor not in span_descriptors:
            fallback_descriptors.append(descriptor)

    fallback_markup = "".join(_fallback_marker_html(descriptor) for descriptor in fallback_descriptors)
    return f"<p class='recipe-sentence'>{''.join(parts)}{fallback_markup}</p>"


def _highlight_span_html(text: str, descriptor: DescriptorMatch) -> str:
    category_code = descriptor.category_code or "OTHER_VDD"
    color = CATEGORY_COLORS.get(category_code, CATEGORY_COLORS["OTHER_VDD"])
    label = escape(CATEGORY_LABELS.get(category_code, "Visual descriptor"))
    tooltip = escape(f"{label}: {descriptor.descriptor_text}")
    return (
        "<span class='vdd-highlight' "
        f"style='--vdd-color: {color};' "
        f"title='{tooltip}' "
        f"aria-label='{tooltip}'>"
        f"{escape(text)}"
        "</span>"
    )


def _fallback_marker_html(descriptor: DescriptorMatch) -> str:
    label = CATEGORY_LABELS.get(descriptor.category_code, "Visual descriptor")
    marker = f"{label}: {descriptor.descriptor_text}"
    return (
        "<span class='vdd-fallback-marker' "
        f"title='{escape(marker)}' "
        f"aria-label='{escape(marker)}'>"
        f"{escape(descriptor.descriptor_text)} cue"
        "</span>"
    )
