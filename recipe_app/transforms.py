from __future__ import annotations

from .models import RecipeDocument, TransformedRecipe


class TransformationService:
    def transform(self, recipe: RecipeDocument) -> TransformedRecipe:
        has_distinct_version_two = (
            recipe.version_two_ingredients != recipe.ingredients
            or recipe.version_two_steps != recipe.steps
        )
        return TransformedRecipe(
            recipe_id=recipe.recipe_id,
            title=recipe.title,
            category=recipe.category,
            url=recipe.url,
            ingredients=recipe.version_two_ingredients,
            steps=recipe.version_two_steps,
            status="excel_version_2" if has_distinct_version_two else "pending_conversion",
            note=(
                "Loaded from workbook version-2 fields."
                if has_distinct_version_two
                else "Automatic non-visual rewriting is not implemented yet. "
                "This panel currently mirrors Version 1."
            ),
        )
