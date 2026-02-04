"""Management command to create system user and default ingredients."""

import csv
import logging
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from planner.models import Ingredient

User = get_user_model()

INGREDIENTS_CSV_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "ingredients.csv"


def load_ingredients_from_csv(path: Path) -> list[dict]:
    """Read ingredients from CSV (delimiter ';', header: name, calories, protein, fat, carbs)."""
    rows = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            name = (row.get("Название ингредиента") or "").strip()
            if not name:
                continue
            try:
                rows.append({
                    "name": name,
                    "calories": int(row.get("Ккал", 0)),
                    "protein": int(row.get("Белки", 0)),
                    "fat": int(row.get("Жиры", 0)),
                    "carbs": int(row.get("Углеводы", 0)),
                })
            except (ValueError, TypeError):
                continue
    return rows


class Command(BaseCommand):
    help = "Create system user and default ingredients."

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

        if not INGREDIENTS_CSV_PATH.exists():
            logger.error("Ingredients CSV not found: %s", INGREDIENTS_CSV_PATH)
            self.stderr.write(self.style.ERROR(f"Ingredients CSV not found: {INGREDIENTS_CSV_PATH}"))
            return

        ingredients = load_ingredients_from_csv(INGREDIENTS_CSV_PATH)
        for data in ingredients:
            _, created = Ingredient.objects.get_or_create(
                user=system_user,
                name=data["name"],
                defaults={
                    "calories": data["calories"],
                    "protein": data["protein"],
                    "fat": data["fat"],
                    "carbs": data["carbs"],
                },
            )
            if created:
                logger.info("Created ingredient: %s", data["name"])

        self.stdout.write(self.style.SUCCESS("Default ingredients populated."))
