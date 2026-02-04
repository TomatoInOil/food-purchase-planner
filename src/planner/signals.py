"""Signals for planner models."""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from planner.models import RecipeIngredient

logger = logging.getLogger(__name__)


@receiver(post_save, sender=RecipeIngredient)
@receiver(post_delete, sender=RecipeIngredient)
def recalculate_recipe_nutrition(sender, instance, **kwargs):
    """Update cached nutrition fields on the parent recipe when ingredients change."""
    try:
        instance.recipe.recalculate_nutrition()
        instance.recipe.save(
            update_fields=[
                "total_calories",
                "total_protein",
                "total_fat",
                "total_carbs",
            ]
        )
    except Exception as e:
        logger.exception("Failed to recalculate recipe nutrition: %s", e)
