from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .config import CORPUS_INSIGHTS_PATH
from .data_loader import RecipeStore


def build_corpus_insights(
    recipe_store: RecipeStore,
    *,
    output_path: str | Path = CORPUS_INSIGHTS_PATH,
) -> dict[str, object]:
    descriptor_code_counts: Counter[str] = Counter()
    top_recipes_by_category: dict[str, list[dict[str, object]]] = {}
    top_recipes_by_descriptor_code: dict[str, list[dict[str, object]]] = defaultdict(list)

    recipes = recipe_store.list_recipes()
    category_groups: dict[str, list] = defaultdict(list)
    for recipe in recipes:
        category_groups[recipe.category].append(recipe)
        for descriptor_code, count in recipe.descriptor_code_counts.items():
            descriptor_code_counts[descriptor_code] += count
            top_recipes_by_descriptor_code[descriptor_code].append(
                {
                    "recipe_id": recipe.recipe_id,
                    "title": recipe.title,
                    "category": recipe.category,
                    "descriptor_count": recipe.descriptor_count,
                    "code_count": count,
                    "star_rating": recipe.star_rating,
                }
            )

    for category, category_recipes in category_groups.items():
        ranked = sorted(
            category_recipes,
            key=lambda recipe: (-recipe.descriptor_count, recipe.title.casefold(), recipe.recipe_id),
        )
        top_recipes_by_category[category] = [
            {
                "recipe_id": recipe.recipe_id,
                "title": recipe.title,
                "descriptor_count": recipe.descriptor_count,
                "star_rating": recipe.star_rating,
            }
            for recipe in ranked[:3]
        ]

    for descriptor_code, recipe_rows in top_recipes_by_descriptor_code.items():
        top_recipes_by_descriptor_code[descriptor_code] = sorted(
            recipe_rows,
            key=lambda row: (-int(row["code_count"]), str(row["title"]).casefold(), str(row["recipe_id"])),
        )[:5]

    insights = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "descriptor_code_counts": dict(sorted(descriptor_code_counts.items(), key=lambda item: (-item[1], item[0]))),
        "top_recipes_by_category": top_recipes_by_category,
        "top_recipes_by_descriptor_code": dict(top_recipes_by_descriptor_code),
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(insights, indent=2), encoding="utf-8")
    return insights
