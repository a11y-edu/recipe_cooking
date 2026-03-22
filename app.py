from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import streamlit as st

from recipe_app.analytics import build_corpus_insights
from recipe_app.config import (
    APP_VERSION,
    PANEL_ONE_VERSION,
    PANEL_TWO_VERSION,
    WORKBOOK_PATH,
)
from recipe_app.data_loader import RecipeStore, build_recipe_document, load_recipe_store
from recipe_app.feedback import FeedbackLogger
from recipe_app.rag import RecipeRAG, RecipeRAGError
from recipe_app.rendering import (
    APP_CSS,
    render_chat_panel_html,
    render_descriptor_tags_html,
    render_recipe_panel_html,
)
from recipe_app.transforms import TransformationService
from recipe_app.supabase_store import SupabaseRecipeStore, SupabaseStoreError

st.set_page_config(
    page_title="Accessible Recipe Prototype",
    page_icon="🍲",
    layout="wide",
)


@st.cache_resource(show_spinner=False)
def get_supabase_store() -> SupabaseRecipeStore:
    return SupabaseRecipeStore()


@st.cache_resource(show_spinner=False)
def get_recipe_store() -> RecipeStore:
    supabase_store = get_supabase_store()
    workbook_store = load_recipe_store(WORKBOOK_PATH) if WORKBOOK_PATH.exists() else None
    try:
        return supabase_store.load_or_sync_recipe_store(workbook_store)
    except SupabaseStoreError as exc:
        if workbook_store is not None:
            return workbook_store
        raise RuntimeError(
            "Recipes could not be loaded. Either provide the local workbook at "
            f"{WORKBOOK_PATH} or configure SUPABASE_URL plus a Supabase API key."
        ) from exc


@st.cache_resource(show_spinner=False)
def get_feedback_logger() -> FeedbackLogger:
    return FeedbackLogger(supabase_store=get_supabase_store())


@st.cache_resource(show_spinner=False)
def get_transformer() -> TransformationService:
    return TransformationService()


@st.cache_resource(show_spinner=False)
def get_rag() -> RecipeRAG:
    return RecipeRAG(supabase_store=get_supabase_store())


@st.cache_resource(show_spinner=False)
def get_corpus_insights() -> dict[str, object]:
    return build_corpus_insights(get_recipe_store())


def main() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)

    try:
        recipe_store = get_recipe_store()
        corpus_insights = get_corpus_insights()
    except RuntimeError as exc:
        st.error(str(exc))
        return
    feedback_logger = get_feedback_logger()
    transformer = get_transformer()
    rag = get_rag()

    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("selected_recipe_id", None)
    st.session_state.setdefault("chat_histories", {})
    st.session_state.setdefault("show_add_recipe_form", False)

    selected_recipe = render_sidebar(recipe_store, corpus_insights, get_supabase_store(), transformer)
    if not selected_recipe:
        st.warning("No recipe matched the current search query.")
        return

    transformed_recipe = transformer.transform(selected_recipe)
    panel_one, panel_two = st.columns(2, gap="medium")

    with panel_one:
        st.markdown(
            render_recipe_panel_html(
                selected_recipe,
                panel_label=f"Version 1: {selected_recipe.title}",
            ),
            unsafe_allow_html=True,
        )
        if st.button("I like Version 1", key=f"panel-1-like-{selected_recipe.recipe_id}"):
            feedback_logger.log_preference(
                session_id=st.session_state["session_id"],
                recipe_id=selected_recipe.recipe_id,
                panel_id="panel_1",
                content_version=PANEL_ONE_VERSION,
            )
            st.success("Saved your preference for Version 1.")

    with panel_two:
        st.markdown(
            render_recipe_panel_html(
                transformed_recipe,
                panel_label=f"Version 2: {transformed_recipe.title}",
            ),
            unsafe_allow_html=True,
        )
        if st.button("I like Version 2", key=f"panel-2-like-{selected_recipe.recipe_id}"):
            feedback_logger.log_preference(
                session_id=st.session_state["session_id"],
                recipe_id=selected_recipe.recipe_id,
                panel_id="panel_2",
                content_version=PANEL_TWO_VERSION,
            )
            st.success("Saved your preference for Version 2.")

    with st.container():
        st.markdown(render_chat_panel_html(selected_recipe), unsafe_allow_html=True)
        chat_history = st.session_state["chat_histories"].setdefault(selected_recipe.recipe_id, [])
        if not rag.is_configured():
            st.warning(
                "Set OPENROUTER_API_KEY in your environment before using the chatbot. "
                "Use a rotated key rather than the one previously shared in chat."
            )

        transcript_container = st.container()
        with transcript_container:
            if chat_history:
                for message in chat_history:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

        prompt = st.chat_input(
            "Ask a question about the selected recipe",
            key=f"chat-input-{selected_recipe.recipe_id}",
            disabled=not rag.is_configured(),
        )
        if prompt:
            user_text = prompt.strip()
            if user_text:
                chat_history.append({"role": "user", "content": user_text})
                try:
                    with st.status("Retrieving grounded recipe context...", expanded=False) as status:
                        answer = rag.answer(selected_recipe, user_text, chat_history[:-1])
                        status.update(label="Grounded response ready.", state="complete")
                except RecipeRAGError as exc:
                    answer = f"Chatbot error: {exc}"

                chat_history.append({"role": "assistant", "content": answer})
                st.rerun()

    st.caption(f"Accessible Recipe Prototype v{APP_VERSION}")


def render_sidebar(
    recipe_store: RecipeStore,
    corpus_insights: dict[str, object],
    supabase_store: SupabaseRecipeStore,
    transformer: TransformationService,
):
    st.sidebar.header("Find a recipe")
    st.session_state.setdefault("sidebar_title_query", "")
    st.session_state.setdefault("sidebar_recipe_id_query", "")
    _apply_pending_sidebar_sync(recipe_store)

    query = st.sidebar.text_input(
        "Search by recipe title",
        key="sidebar_title_query",
        placeholder="Start typing a title",
    )
    recipe_id_query = st.sidebar.text_input(
        "Search by recipe ID",
        key="sidebar_recipe_id_query",
        placeholder="Example: AP01",
    )

    all_categories = sorted({recipe.category for recipe in recipe_store.recipes.values()})
    st.session_state.setdefault("sidebar_selected_categories", all_categories)
    selected_categories = st.sidebar.multiselect(
        "Recipe categories",
        options=all_categories,
        key="sidebar_selected_categories",
    )

    ratings = [recipe.star_rating for recipe in recipe_store.recipes.values() if recipe.star_rating is not None]
    minimum_rating = min(ratings) if ratings else 0.0
    maximum_rating = max(ratings) if ratings else 5.0
    rating_range = st.sidebar.slider(
        "Star rating range",
        min_value=float(minimum_rating),
        max_value=float(maximum_rating),
        value=(float(minimum_rating), float(maximum_rating)),
        step=0.1,
    )

    descriptor_code_counts = corpus_insights["descriptor_code_counts"]
    st.sidebar.markdown("#### Descriptor code shortcuts")
    st.sidebar.markdown(render_descriptor_tags_html(descriptor_code_counts), unsafe_allow_html=True)
    selected_descriptor_codes = st.sidebar.multiselect(
        "Filter by descriptor code",
        options=list(descriptor_code_counts.keys()),
        format_func=lambda code: f"{code} ({descriptor_code_counts[code]})",
    )
    st.sidebar.caption("Saved corpus insights: `local_data/corpus_insights.json`")

    with st.sidebar.expander("Top 3 VDD-heavy recipes in each category", expanded=False):
        for category in all_categories:
            st.markdown(f"**{category}**")
            for row in corpus_insights["top_recipes_by_category"].get(category, []):
                label = (
                    f"{row['recipe_id']} • {row['title']} "
                    f"({row['descriptor_count']} VDDs)"
                )
                if st.button(label, key=f"top-{category}-{row['recipe_id']}", use_container_width=True):
                    selected_recipe_id = row["recipe_id"]
                    _queue_sidebar_sync(selected_recipe_id)
                    st.rerun()

    matches = recipe_store.filter_recipes(
        title_query=query,
        recipe_id_query=recipe_id_query,
        categories=selected_categories,
        rating_range=rating_range,
        descriptor_codes=selected_descriptor_codes,
    )
    st.sidebar.caption(f"{len(matches)} matching recipes")

    if not matches:
        _render_database_actions(recipe_store, supabase_store, transformer)
        return None

    allowed_ids = [recipe.recipe_id for recipe in matches]
    selected_recipe_id = st.session_state.get("selected_recipe_id")
    selection_was_reset = False
    if selected_recipe_id not in allowed_ids:
        selected_recipe_id = allowed_ids[0]
        st.session_state["selected_recipe_id"] = selected_recipe_id
        selection_was_reset = True

    chosen_recipe_id = st.sidebar.selectbox(
        "Matching recipes",
        options=allowed_ids,
        index=allowed_ids.index(selected_recipe_id),
        format_func=lambda recipe_id: (
            f"{recipe_id} • {recipe_store.get(recipe_id).title} "
            f"[{recipe_store.get(recipe_id).category}] "
            f"★{recipe_store.get(recipe_id).star_rating if recipe_store.get(recipe_id).star_rating is not None else 'NA'} "
            f"• {recipe_store.get(recipe_id).descriptor_count} VDDs"
        ),
    )
    if chosen_recipe_id != selected_recipe_id:
        _queue_sidebar_sync(chosen_recipe_id)
        st.rerun()

    if not selection_was_reset:
        st.session_state["selected_recipe_id"] = chosen_recipe_id
    _render_database_actions(recipe_store, supabase_store, transformer)
    return recipe_store.get(chosen_recipe_id)


def _queue_sidebar_sync(recipe_id: str) -> None:
    st.session_state["pending_sidebar_sync_recipe_id"] = recipe_id
    st.session_state["selected_recipe_id"] = recipe_id


def _apply_pending_sidebar_sync(recipe_store: RecipeStore) -> None:
    pending_recipe_id = st.session_state.pop("pending_sidebar_sync_recipe_id", None)
    if not pending_recipe_id:
        return
    selected_recipe = recipe_store.get(pending_recipe_id)
    st.session_state["selected_recipe_id"] = pending_recipe_id
    st.session_state["sidebar_title_query"] = selected_recipe.title
    st.session_state["sidebar_recipe_id_query"] = pending_recipe_id
    st.session_state["sidebar_selected_categories"] = [selected_recipe.category]


def _render_database_actions(
    recipe_store: RecipeStore,
    supabase_store: SupabaseRecipeStore,
    transformer: TransformationService,
) -> None:
    st.sidebar.markdown("#### Database")
    is_supabase_ready = supabase_store.is_configured()
    export_payload = _build_export_payload(recipe_store, supabase_store, transformer)
    reset_column, add_column, export_column = st.sidebar.columns(3)

    with reset_column:
        if st.button("Reset", use_container_width=True, disabled=not is_supabase_ready):
            if not WORKBOOK_PATH.exists():
                st.sidebar.error(f"Workbook not found at `{WORKBOOK_PATH}`.")
            else:
                try:
                    workbook_store = load_recipe_store(WORKBOOK_PATH)
                    supabase_store.reset_recipes_from_store(workbook_store)
                    selected_recipe_id = st.session_state.get("selected_recipe_id")
                    if selected_recipe_id not in workbook_store.recipes:
                        selected_recipe_id = workbook_store.list_recipes()[0].recipe_id
                    _clear_data_caches()
                    _queue_sidebar_sync(selected_recipe_id)
                    st.session_state["show_add_recipe_form"] = False
                    st.rerun()
                except SupabaseStoreError as exc:
                    st.sidebar.error(f"Reset failed: {exc}")

    with add_column:
        if st.button("Add recipe", use_container_width=True, disabled=not is_supabase_ready):
            st.session_state["show_add_recipe_form"] = not st.session_state.get("show_add_recipe_form", False)

    with export_column:
        st.download_button(
            "Export",
            data=export_payload,
            file_name=f"recipes-export-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            disabled=not export_payload,
        )

    st.sidebar.caption(
        "Reset clears the app-managed recipe tables in Supabase and reloads them from the Excel workbook."
    )

    if st.session_state.get("show_add_recipe_form"):
        _render_add_recipe_form(recipe_store, supabase_store)


def _render_add_recipe_form(recipe_store: RecipeStore, supabase_store: SupabaseRecipeStore) -> None:
    with st.sidebar.form("add-recipe-form"):
        st.markdown("#### Add a recipe")
        recipe_id = st.text_input("Recipe ID", placeholder="Example: MX01")
        title = st.text_input("Recipe name")
        category = st.text_input("Recipe category")
        url = st.text_input("Original URL", placeholder="Optional")
        star_rating_text = st.text_input("Star rating", placeholder="Optional, 0 to 5")
        review_count_text = st.text_input("Review count", placeholder="Optional integer")
        ingredients_text = st.text_area("Ingredients", placeholder="One ingredient per line")
        steps_text = st.text_area("Steps", placeholder="One step per line")
        version_two_ingredients_text = st.text_area(
            "Version 2 ingredients",
            placeholder="Optional. One ingredient per line. Leave blank to mirror Version 1.",
        )
        version_two_steps_text = st.text_area(
            "Version 2 steps",
            placeholder="Optional. One step per line. Leave blank to mirror Version 1.",
        )
        save_column, cancel_column = st.columns(2)
        with save_column:
            submitted = st.form_submit_button("Save recipe", use_container_width=True)
        with cancel_column:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

    if cancelled:
        st.session_state["show_add_recipe_form"] = False
        st.rerun()

    if not submitted:
        return

    normalized_recipe_id = recipe_id.strip().upper()
    normalized_title = title.strip()
    normalized_category = category.strip()
    normalized_url = url.strip()
    ingredient_lines = [line.strip() for line in ingredients_text.splitlines() if line.strip()]
    step_lines = [line.strip() for line in steps_text.splitlines() if line.strip()]
    version_two_ingredient_lines = [
        line.strip() for line in version_two_ingredients_text.splitlines() if line.strip()
    ]
    version_two_step_lines = [line.strip() for line in version_two_steps_text.splitlines() if line.strip()]
    errors: list[str] = []

    if not normalized_recipe_id:
        errors.append("Recipe ID is required.")
    if normalized_recipe_id in recipe_store.recipes:
        errors.append(f"Recipe ID `{normalized_recipe_id}` already exists.")
    if not normalized_title:
        errors.append("Recipe name is required.")
    if not normalized_category:
        errors.append("Recipe category is required.")
    if not step_lines:
        errors.append("At least one step is required.")

    star_rating = None
    if star_rating_text.strip():
        try:
            star_rating = float(star_rating_text.strip())
        except ValueError:
            errors.append("Star rating must be a number.")
        else:
            if not 0.0 <= star_rating <= 5.0:
                errors.append("Star rating must be between 0 and 5.")

    review_count = None
    if review_count_text.strip():
        try:
            review_count = int(review_count_text.strip())
        except ValueError:
            errors.append("Review count must be an integer.")

    if errors:
        st.sidebar.error(" ".join(errors))
        return

    recipe = build_recipe_document(
        recipe_id=normalized_recipe_id,
        title=normalized_title,
        category=normalized_category,
        url=normalized_url,
        star_rating=star_rating,
        review_count=review_count,
        ingredient_lines=ingredient_lines,
        step_lines=step_lines,
        version_two_ingredient_lines=version_two_ingredient_lines or None,
        version_two_step_lines=version_two_step_lines or None,
    )
    try:
        supabase_store.upsert_recipe(recipe)
        _clear_data_caches()
        st.session_state["show_add_recipe_form"] = False
        _queue_sidebar_sync(recipe.recipe_id)
        st.rerun()
    except SupabaseStoreError as exc:
        st.sidebar.error(f"Could not add recipe: {exc}")


def _build_export_payload(
    recipe_store: RecipeStore,
    supabase_store: SupabaseRecipeStore,
    transformer: TransformationService,
) -> str:
    vote_counts = supabase_store.get_feedback_vote_counts()
    recipes_payload = []
    for recipe in recipe_store.list_recipes():
        transformed = transformer.transform(recipe)
        recipe_votes = vote_counts.get(recipe.recipe_id, {})
        recipes_payload.append(
            {
                "recipe_id": recipe.recipe_id,
                "title": recipe.title,
                "category": recipe.category,
                "url": recipe.url,
                "star_rating": recipe.star_rating,
                "review_count": recipe.review_count,
                "descriptor_count": recipe.descriptor_count,
                "descriptor_code_counts": recipe.descriptor_code_counts,
                "votes": {
                    "version_1": int(recipe_votes.get("panel_1", 0)),
                    "version_2": int(recipe_votes.get("panel_2", 0)),
                },
                "versions": {
                    "version_1": {
                        "content_version": PANEL_ONE_VERSION,
                        "ingredients": [ingredient.full_text for ingredient in recipe.ingredients],
                        "steps": [
                            " ".join(sentence.text for sentence in step.sentences)
                            for step in recipe.steps
                        ],
                    },
                    "version_2": {
                        "content_version": PANEL_TWO_VERSION,
                        "status": transformed.status,
                        "ingredients": [ingredient.full_text for ingredient in transformed.ingredients],
                        "steps": [
                            " ".join(sentence.text for sentence in step.sentences)
                            for step in transformed.steps
                        ],
                    },
                },
            }
        )
    return json.dumps(
        {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "recipe_count": len(recipes_payload),
            "recipes": recipes_payload,
        },
        indent=2,
    )


def _clear_data_caches() -> None:
    get_recipe_store.clear()
    get_corpus_insights.clear()


if __name__ == "__main__":
    main()
