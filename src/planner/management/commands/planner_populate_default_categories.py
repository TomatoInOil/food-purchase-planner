"""Management command to create system user and default recipe categories."""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from planner.models import RecipeCategory

User = get_user_model()

DEFAULT_CATEGORIES = [
    "Первые блюда",
    "Вторые блюда",
    "Салаты",
    "Закуски",
    "Десерты",
    "Выпечка",
    "Завтрак",
    "Напитки",
]


class Command(BaseCommand):
    help = "Create system user and default recipe categories."

    def handle(self, *args, **options):
        logger = logging.getLogger(__name__)
        system_user, created = User.objects.get_or_create(
            username="system",
            defaults={"is_active": False},
        )
        if created:
            logger.info("Created system user")

        for name in DEFAULT_CATEGORIES:
            _, created = RecipeCategory.objects.get_or_create(
                user=system_user,
                name=name,
            )
            if created:
                logger.info("Created category: %s", name)

        self.stdout.write(self.style.SUCCESS("Default recipe categories populated."))
