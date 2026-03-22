from __future__ import annotations

from .models import RecipeDocument, TransformedRecipe


class TransformationService:
    def transform(self, recipe: RecipeDocument) -> TransformedRecipe:
        return TransformedRecipe(
            recipe_id=recipe.recipe_id,
            title=recipe.title,
            category=recipe.category,
            url=recipe.url,
            ingredients=recipe.ingredients,
            steps=recipe.steps,
            status="pending_conversion",
            note=(
                "Automatic non-visual rewriting is not implemented yet. "
                "This panel currently mirrors the canonical recipe so preference logging can start now."
            ),
        )
