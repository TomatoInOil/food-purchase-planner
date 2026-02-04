"""Management command to create system user and default ingredients."""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from planner.models import Ingredient

User = get_user_model()

DEFAULT_INGREDIENTS = [
    {"name": "Куриная грудка", "calories": 165, "protein": 31, "fat": 3.6, "carbs": 0},
    {"name": "Рис", "calories": 130, "protein": 2.7, "fat": 0.3, "carbs": 28},
    {"name": "Брокколи", "calories": 34, "protein": 2.8, "fat": 0.4, "carbs": 7},
    {"name": "Яйцо", "calories": 155, "protein": 13, "fat": 11, "carbs": 1.1},
    {"name": "Овсянка", "calories": 389, "protein": 16.9, "fat": 6.9, "carbs": 66.3},
    {"name": "Банан", "calories": 89, "protein": 1.1, "fat": 0.3, "carbs": 23},
    {"name": "Греческий йогурт", "calories": 59, "protein": 10, "fat": 0.4, "carbs": 3.6},
    {"name": "Лосось", "calories": 208, "protein": 20, "fat": 13, "carbs": 0},
]


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

        for data in DEFAULT_INGREDIENTS:
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
