"""Domain services for menu and shopping list calculations."""

from datetime import timedelta

from planner.models import MenuSlot, RecipeIngredient


def get_menu_for_user(user):
    """
    Build menu dict from MenuSlot for the given user.
    Returns {"day-meal": recipe_id} with None for empty slots.
    """
    slots = MenuSlot.objects.filter(user=user)
    data = {f"{s.day_of_week}-{s.meal_type}": s.recipe_id for s in slots}
    for day in range(7):
        for meal in range(4):
            key = f"{day}-{meal}"
            if key not in data:
                data[key] = None
    return data


def calculate_shopping_list_for_user(user, start_date, end_date, people_count=2):
    """
    Compute aggregated shopping list for the user's weekly menu over the date range.
    Returns list of {"name": str, "weight_grams": int} sorted by name.
    """
    slots_by_day_meal = {
        (s.day_of_week, s.meal_type): s.recipe_id
        for s in MenuSlot.objects.filter(user=user)
    }
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
    result = [
        {"name": v["name"], "weight_grams": round(v["weight_grams"] * people_count)}
        for v in aggregated.values()
    ]
    result.sort(key=lambda x: x["name"])
    return result
