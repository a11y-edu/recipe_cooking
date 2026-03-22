from __future__ import annotations

import uuid

import streamlit as st

from recipe_app.analytics import build_corpus_insights
from recipe_app.config import (
    APP_VERSION,
    PANEL_ONE_VERSION,
    PANEL_TWO_VERSION,
    WORKBOOK_PATH,
)
from recipe_app.data_loader import RecipeStore, load_recipe_store
from recipe_app.feedback import FeedbackLogger
from recipe_app.rag import RecipeRAG, RecipeRAGError
from recipe_app.rendering import (
    APP_CSS,
    render_chat_panel_html,
    render_descriptor_tags_html,
    render_recipe_panel_html,
)
from recipe_app.transforms import TransformationService

st.set_page_config(
    page_title="Accessible Recipe Prototype",
    page_icon="🍲",
    layout="wide",
)


@st.cache_resource(show_spinner=False)
def get_recipe_store() -> RecipeStore:
    return load_recipe_store(WORKBOOK_PATH)


@st.cache_resource(show_spinner=False)
def get_feedback_logger() -> FeedbackLogger:
    return FeedbackLogger()


@st.cache_resource(show_spinner=False)
def get_transformer() -> TransformationService:
    return TransformationService()


@st.cache_resource(show_spinner=False)
def get_rag() -> RecipeRAG:
    return RecipeRAG()


@st.cache_resource(show_spinner=False)
def get_corpus_insights() -> dict[str, object]:
    return build_corpus_insights(get_recipe_store())


def main() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)

    recipe_store = get_recipe_store()
    corpus_insights = get_corpus_insights()
    feedback_logger = get_feedback_logger()
    transformer = get_transformer()
    rag = get_rag()

    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("selected_recipe_id", None)
    st.session_state.setdefault("chat_histories", {})

    selected_recipe = render_sidebar(recipe_store, corpus_insights)
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


def render_sidebar(recipe_store: RecipeStore, corpus_insights: dict[str, object]):
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


if __name__ == "__main__":
    main()
