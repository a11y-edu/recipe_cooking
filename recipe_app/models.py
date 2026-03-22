from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class IngredientLine:
    line_number: int
    full_text: str
    quantity: str | None = None
    unit: str | None = None
    ingredient_name: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class DescriptorMatch:
    step_number: int
    sentence_number: int
    descriptor_text: str
    category_code: str
    multimodal_flag: bool | None
    redundant_flag: bool | None
    span_start: int | None = None
    span_end: int | None = None
    match_type: str = "sentence"


@dataclass(slots=True)
class RecipeSentence:
    step_number: int
    sentence_number: int
    text: str
    descriptors: list[DescriptorMatch] = field(default_factory=list)


@dataclass(slots=True)
class RecipeStep:
    step_number: int
    sentences: list[RecipeSentence] = field(default_factory=list)


@dataclass(slots=True)
class RecipeChunk:
    chunk_id: str
    title: str
    text: str


@dataclass(slots=True)
class RecipeDocument:
    recipe_id: str
    title: str
    category: str
    url: str
    star_rating: float | None
    review_count: int | None
    ingredients: list[IngredientLine]
    steps: list[RecipeStep]
    descriptors: list[DescriptorMatch]
    descriptor_count: int
    descriptor_code_counts: dict[str, int]
    chatbot_context: str
    chunks: list[RecipeChunk]


@dataclass(slots=True)
class TransformedRecipe:
    recipe_id: str
    title: str
    category: str
    url: str
    ingredients: list[IngredientLine]
    steps: list[RecipeStep]
    status: str
    note: str


@dataclass(slots=True)
class FeedbackEvent:
    timestamp: str
    session_id: str
    recipe_id: str
    panel_id: str
    content_version: str
    app_version: str
