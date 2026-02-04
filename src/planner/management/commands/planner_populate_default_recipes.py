"""Management command to create system user and default recipes from CSV."""

import csv
import logging
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from planner.models import Ingredient, Recipe, RecipeIngredient

User = get_user_model()

RECIPES_CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent / "data" / "recipes.csv"
)


def load_recipes_from_csv(path: Path) -> list[dict]:
    """Read recipe rows from CSV (delimiter ';', fields: Название блюда, Ингредиент, Вес (г))."""
    rows = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            recipe_name = (row.get("Название блюда") or "").strip()
            ingredient_name = (row.get("Ингредиент") or "").strip()
            if not recipe_name or not ingredient_name:
                continue
            try:
                weight_grams = int(row.get("Вес (г)", 0))
            except (ValueError, TypeError):
                continue
            rows.append(
                {
                    "recipe_name": recipe_name,
                    "ingredient_name": ingredient_name,
                    "weight_grams": weight_grams,
                }
            )
    return rows


class Command(BaseCommand):
    help = "Create system user and default recipes from CSV."

    def handle(self, *args, **options):
        logger = logging.getLogger(__name__)
        system_user, created = User.objects.get_or_create(
            username="system",
            defaults={"is_active": False},
        )
        if created:
            logger.info("Created system user")
        else:
            logger.debug("System user already exists")

        if not RECIPES_CSV_PATH.exists():
            logger.error("Recipes CSV not found: %s", RECIPES_CSV_PATH)
            self.stderr.write(
                self.style.ERROR(f"Recipes CSV not found: {RECIPES_CSV_PATH}")
            )
            return

        rows = load_recipes_from_csv(RECIPES_CSV_PATH)
        for data in rows:
            recipe, recipe_created = Recipe.objects.get_or_create(
                user=system_user,
                name=data["recipe_name"],
                defaults={"description": "", "instructions": ""},
            )
            if recipe_created:
                logger.info("Created recipe: %s", data["recipe_name"])

            ingredient = Ingredient.objects.filter(
                user=system_user,
                name=data["ingredient_name"],
            ).first()
            if not ingredient:
                logger.warning(
                    "Ingredient not found, skipping row: %s / %s",
                    data["recipe_name"],
                    data["ingredient_name"],
                )
                continue

            _, ri_created = RecipeIngredient.objects.update_or_create(
                recipe=recipe,
                ingredient=ingredient,
                defaults={"weight_grams": data["weight_grams"]},
            )
            if ri_created:
                logger.info(
                    "Added ingredient %s to recipe %s",
                    data["ingredient_name"],
                    data["recipe_name"],
                )

        self.stdout.write(self.style.SUCCESS("Default recipes populated."))
