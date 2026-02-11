"""Domain services for menu and shopping list calculations."""

import logging
from datetime import timedelta

from planner.models import Menu, MenuSlot, RecipeIngredient

logger = logging.getLogger(__name__)


def get_or_create_first_menu(user):
    """Return the user's first (oldest) menu, creating a default one if none exists."""
    menu = Menu.objects.filter(user=user).first()
    if not menu:
        menu = Menu.objects.create(user=user, name="Меню на неделю")
        logger.info("Created default menu for user_id=%s", user.pk)
    return menu


def get_menu_slots(menu):
    """
    Build menu dict from MenuSlot for the given Menu.
    Returns {"day-meal": recipe_id} with None for empty slots.
    """
    slots = MenuSlot.objects.filter(menu=menu)
    data = {f"{s.day_of_week}-{s.meal_type}": s.recipe_id for s in slots}
    for day in range(7):
        for meal in range(4):
            key = f"{day}-{meal}"
            if key not in data:
                data[key] = None
    return data


def get_menu_for_user(user):
    """
    Build menu dict for the user's first menu.
    Backward-compatible wrapper around get_menu_slots.
    """
    menu = get_or_create_first_menu(user)
    return get_menu_slots(menu)


def calculate_shopping_list(menu, start_date, end_date, people_count=2):
    """
    Compute aggregated shopping list for a specific menu over the date range.
    Returns list of {"name": str, "weight_grams": int} sorted by name.
    """
    slots_by_day_meal = {
        (s.day_of_week, s.meal_type): s.recipe_id
        for s in MenuSlot.objects.filter(menu=menu)
    }
    aggregated = _aggregate_ingredients(slots_by_day_meal, start_date, end_date)
    result = _build_shopping_result(aggregated, people_count)
    logger.info(
        "Shopping list for menu_id=%s (%s — %s, people=%d): %d items",
        menu.pk, start_date, end_date, people_count, len(result),
    )
    return result


def calculate_shopping_list_for_user(user, start_date, end_date, people_count=2):
    """
    Compute shopping list for the user's first menu.
    Backward-compatible wrapper around calculate_shopping_list.
    """
    menu = get_or_create_first_menu(user)
    return calculate_shopping_list(menu, start_date, end_date, people_count)


def _aggregate_ingredients(slots_by_day_meal, start_date, end_date):
    """Walk date range and collect ingredient weights from recipe slots."""
    aggregated = {}
    current = start_date
    while current <= end_date:
        day_of_week = current.weekday()
        for meal_type in range(4):
            recipe_id = slots_by_day_meal.get((day_of_week, meal_type))
            if not recipe_id:
                continue
            for ri in RecipeIngredient.objects.filter(
                recipe_id=recipe_id
            ).select_related("ingredient"):
                ing_id = ri.ingredient_id
                if ing_id not in aggregated:
                    aggregated[ing_id] = {
                        "name": ri.ingredient.name,
                        "weight_grams": 0,
                    }
                aggregated[ing_id]["weight_grams"] += ri.weight_grams
        current += timedelta(days=1)
    return aggregated


def _build_shopping_result(aggregated, people_count):
    """Format aggregated ingredients into sorted list with people multiplier."""
    result = [
        {"name": v["name"], "weight_grams": round(v["weight_grams"] * people_count)}
        for v in aggregated.values()
    ]
    result.sort(key=lambda x: x["name"])
    return result
