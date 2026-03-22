from __future__ import annotations

from html import escape

from .config import CATEGORY_COLORS
from .highlighting import render_sentence_html
from .models import RecipeDocument, TransformedRecipe

APP_CSS = """
<style>
:root {
    --bg-cream: #f7f1e8;
    --bg-sand: #efe4d3;
    --ink: #1e1c19;
    --muted: #5b5850;
    --card: rgba(255, 249, 241, 0.92);
    --border: rgba(87, 61, 38, 0.18);
    --accent: #b65b3a;
    --accent-soft: #f6d7c7;
    --teal: #2f7a78;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at top right, rgba(47, 122, 120, 0.12), transparent 28%),
        radial-gradient(circle at top left, rgba(182, 91, 58, 0.14), transparent 30%),
        linear-gradient(180deg, var(--bg-cream) 0%, #fbf7f1 45%, var(--bg-sand) 100%);
    color: var(--ink);
}

header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
    display: none;
}

[data-testid="stAppViewContainer"] .main,
[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
    padding-right: 1.1rem;
    padding-bottom: 1rem;
    padding-left: 1.1rem;
    margin-top: 0 !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(255, 248, 240, 0.98), rgba(245, 234, 219, 0.98));
    border-right: 1px solid var(--border);
}

html, body, [class*="css"], [data-testid="stMarkdownContainer"] {
    color: var(--ink);
    font-family: "Avenir Next", "Segoe UI", "Trebuchet MS", sans-serif;
}

h1, h2, h3, h4 {
    font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
    letter-spacing: 0.01em;
}

.hero-card,
.panel-card,
.summary-card,
.chat-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 20px;
    box-shadow: 0 18px 40px rgba(68, 48, 30, 0.08);
}

.hero-card {
    padding: 0.85rem 1.2rem 0.8rem;
    margin-bottom: 0.75rem;
}

.hero-eyebrow,
.panel-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.78rem;
    color: var(--teal);
    font-weight: 700;
}

.hero-title {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 800;
}

.summary-card {
    padding: 0.55rem 0.7rem;
    margin-bottom: 0.45rem;
}

.summary-title {
    margin: 0;
    font-size: 0.96rem;
    line-height: 1.1;
}

.summary-title-link {
    text-decoration: none;
    color: var(--ink);
}

.summary-title-link:hover,
.summary-title-link:focus {
    text-decoration: underline;
}

.summary-title-link:visited {
    color: var(--ink);
}

.panel-title-link {
    color: var(--muted);
    font-size: 0.82em;
    font-weight: 700;
    text-decoration: none;
}

.panel-title-link:hover,
.panel-title-link:focus,
.panel-title-link:visited {
    color: var(--muted);
    text-decoration: underline;
}

.summary-title-inline-meta {
    color: var(--muted);
    font-weight: 700;
}

.panel-card,
.chat-card {
    padding: 0.8rem 0.9rem 0.95rem;
}

.panel-card h2,
.chat-card h2 {
    margin: 0 0 0.3rem;
    font-size: 1.28rem;
}

.panel-note {
    margin: 0 0 0.8rem;
    padding: 0.75rem 0.9rem;
    border-left: 4px solid var(--accent);
    background: rgba(182, 91, 58, 0.08);
    border-radius: 0 12px 12px 0;
    color: var(--muted);
}

.panel-section-label {
    margin: 0.75rem 0 0.28rem;
    font-size: 0.78rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--teal);
    font-weight: 700;
}

.ingredient-list,
.step-list {
    margin: 0;
    padding-left: 1rem;
}

.ingredient-list li,
.step-list li {
    margin-bottom: 0.34rem;
}

.recipe-sentence {
    margin: 0 0 0.28rem;
    line-height: 1.45;
}

.vdd-highlight {
    background: color-mix(in srgb, var(--vdd-color) 20%, white);
    border-bottom: 3px solid var(--vdd-color);
    border-radius: 0.3rem;
    padding: 0 0.08rem;
    font-weight: 600;
}

.vdd-fallback-marker {
    display: inline-block;
    margin-left: 0.35rem;
    margin-top: 0.15rem;
    padding: 0.18rem 0.5rem;
    border-radius: 999px;
    font-size: 0.75rem;
    background: rgba(47, 122, 120, 0.12);
    color: var(--teal);
    border: 1px solid rgba(47, 122, 120, 0.18);
}

.legend-copy {
    margin: 0.15rem 0 0.35rem;
    color: var(--muted);
    font-size: 0.9rem;
}

.chat-message {
    padding: 0.65rem 0.75rem;
    border-radius: 14px;
    margin-bottom: 0.5rem;
    line-height: 1.42;
    border: 1px solid var(--border);
}

.chat-message-user {
    background: rgba(182, 91, 58, 0.11);
}

.chat-message-assistant {
    background: rgba(47, 122, 120, 0.09);
}

.chat-role {
    display: block;
    font-size: 0.74rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 700;
    color: var(--muted);
    margin-bottom: 0.3rem;
}

.privacy-note {
    font-size: 0.9rem;
    color: var(--muted);
}

.descriptor-tag-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-top: 0.35rem;
}

.descriptor-tag {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.28rem 0.62rem;
    border-radius: 999px;
    font-size: 0.78rem;
    color: white;
    font-weight: 700;
    letter-spacing: 0.01em;
}

.descriptor-tag strong {
    font-size: 0.72rem;
    opacity: 0.95;
}

.sidebar-insight-copy {
    margin: 0.2rem 0 0.45rem;
    color: var(--muted);
    font-size: 0.9rem;
}

.stButton button {
    width: 100%;
    border-radius: 999px;
    border: 1px solid rgba(182, 91, 58, 0.25);
    background: linear-gradient(180deg, #fbefe7, #f7dacb);
    color: var(--ink);
    font-weight: 700;
}
</style>
"""
def render_recipe_panel_html(
    recipe: RecipeDocument | TransformedRecipe,
    *,
    panel_label: str,
) -> str:
    heading_markup = escape(panel_label)
    if recipe.url:
        heading_markup += (
            " "
            f"(<a class='panel-title-link' href='{escape(recipe.url)}' "
            "target='_blank' rel='noopener noreferrer'>original</a>)"
        )
    ingredient_count = len(recipe.ingredients)
    step_count = len(recipe.steps)
    step_label = "step" if step_count == 1 else "steps"
    ingredients_markup = "".join(
        f"<li>{escape(ingredient.full_text)}</li>"
        for ingredient in recipe.ingredients
    ) or "<li>No ingredients recorded.</li>"
    steps_markup = "".join(
        _render_step_html(step.step_number, step.sentences)
        for step in recipe.steps
    ) or "<li>No steps recorded.</li>"
    return f"""
    <section class="panel-card" role="region" aria-label="{escape(panel_label)}">
        <h2>{heading_markup}</h2>
        <div class="panel-section-label">Ingredients ({ingredient_count})</div>
        <ul class="ingredient-list">
            {ingredients_markup}
        </ul>
        <div class="panel-section-label">Step-by-step Process ({step_count} {step_label})</div>
        <ol class="step-list">
            {steps_markup}
        </ol>
    </section>
    """


def render_chat_panel_html(recipe: RecipeDocument) -> str:
    return f"""
    <section class="chat-card" role="region" aria-label="Recipe chatbot">
        <h2>Recipe Chatbot</h2>
        <p class="legend-copy">
            Ask grounded questions about <strong>{escape(recipe.title)}</strong>. The chatbot retrieves only
            from the selected recipe's ingredients, steps, and descriptor notes.
        </p>
    </section>
    """


def render_descriptor_tags_html(code_counts: dict[str, int]) -> str:
    tags = "".join(
        (
            "<span class='descriptor-tag' "
            f"style='background: {CATEGORY_COLORS.get(code, CATEGORY_COLORS['OTHER_VDD'])};'>"
            f"{escape(code)} <strong>{count}</strong>"
            "</span>"
        )
        for code, count in code_counts.items()
    )
    return (
        "<div>"
        "<p class='sidebar-insight-copy'>Corpus-wide descriptor-code frequency.</p>"
        f"<div class='descriptor-tag-grid'>{tags}</div>"
        "</div>"
    )


def _render_step_html(step_number: int, sentences) -> str:
    sentence_markup = "".join(render_sentence_html(sentence) for sentence in sentences)
    return f"<li aria-label='Step {step_number}'>{sentence_markup}</li>"
