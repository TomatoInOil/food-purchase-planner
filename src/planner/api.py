"""API views for recipes, ingredients, menu, and shopping list."""

import json
import logging
from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from planner.models import Ingredient, MenuSlot, Recipe, RecipeIngredient

logger = logging.getLogger(__name__)


def _error_response(message, status=400):
    return JsonResponse({"error": str(message)}, status=status)


def _ingredient_to_dict(ingredient, is_owner):
    return {
        "id": ingredient.id,
        "name": ingredient.name,
        "calories": ingredient.calories,
        "protein": ingredient.protein,
        "fat": ingredient.fat,
        "carbs": ingredient.carbs,
        "is_owner": is_owner,
    }


def _recipe_to_dict(recipe, is_owner):
    ingredients = [
        {
            "ingredient_id": ri.ingredient_id,
            "ingredient_name": ri.ingredient.name,
            "weight_grams": ri.weight_grams,
        }
        for ri in recipe.recipe_ingredients.select_related("ingredient")
    ]
    return {
        "id": recipe.id,
        "name": recipe.name,
        "description": recipe.description or "",
        "instructions": recipe.instructions or "",
        "total_calories": recipe.total_calories or 0,
        "total_protein": recipe.total_protein or 0,
        "total_fat": recipe.total_fat or 0,
        "total_carbs": recipe.total_carbs or 0,
        "is_owner": is_owner,
        "ingredients": ingredients,
    }


def _is_system_ingredient(ingredient):
    return ingredient.user.username == "system"


# Ingredients
@login_required
@require_http_methods(["GET", "POST"])
def ingredient_list_or_create(request):
    if request.method == "GET":
        return _ingredient_list(request)
    return _ingredient_create(request)


def _ingredient_list(request):
    ingredients = Ingredient.objects.select_related("user").order_by("name")
    data = [
        _ingredient_to_dict(ing, is_owner=(ing.user_id == request.user.id))
        for ing in ingredients
    ]
    return JsonResponse(data, safe=False)


def _ingredient_create(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError as e:
        return _error_response(f"Invalid JSON: {e}")

    name = body.get("name", "").strip()
    if not name:
        return _error_response("name is required")

    try:
        calories = float(body.get("calories", 0))
        protein = float(body.get("protein", 0))
        fat = float(body.get("fat", 0))
        carbs = float(body.get("carbs", 0))
    except (TypeError, ValueError):
        return _error_response("calories, protein, fat, carbs must be numbers")

    if Ingredient.objects.filter(user=request.user, name=name).exists():
        return _error_response("Ingredient with this name already exists", status=400)

    ingredient = Ingredient.objects.create(
        user=request.user,
        name=name,
        calories=calories,
        protein=protein,
        fat=fat,
        carbs=carbs,
    )
    return JsonResponse(_ingredient_to_dict(ingredient, is_owner=True), status=201)


@login_required
@require_http_methods(["DELETE"])
def ingredient_delete(request, pk):
    try:
        ingredient = Ingredient.objects.get(pk=pk)
    except Ingredient.DoesNotExist:
        return JsonResponse({"error": "Ingredient not found"}, status=404)

    if ingredient.user_id != request.user.id:
        return _error_response("Not allowed to delete this ingredient", status=403)

    if _is_system_ingredient(ingredient):
        return _error_response("Cannot delete system ingredient", status=400)

    if RecipeIngredient.objects.filter(ingredient=ingredient).exists():
        return _error_response("Ingredient is used in recipes", status=400)

    ingredient.delete()
    return JsonResponse({"status": "ok"})


# Recipes
@login_required
@require_http_methods(["GET", "POST"])
def recipe_list_or_create(request):
    if request.method == "GET":
        return _recipe_list(request)
    return _recipe_create(request)


def _recipe_list(request):
    recipes = Recipe.objects.prefetch_related("recipe_ingredients__ingredient").order_by(
        "name"
    )
    data = [
        _recipe_to_dict(r, is_owner=(r.user_id == request.user.id)) for r in recipes
    ]
    return JsonResponse(data, safe=False)


@login_required
@require_http_methods(["GET", "PUT", "DELETE"])
def recipe_detail_update_delete(request, pk):
    if request.method == "GET":
        return _recipe_detail(request, pk)
    if request.method == "PUT":
        return _recipe_update(request, pk)
    return _recipe_delete(request, pk)


def _recipe_detail(request, pk):
    try:
        recipe = Recipe.objects.prefetch_related(
            "recipe_ingredients__ingredient"
        ).get(pk=pk)
    except Recipe.DoesNotExist:
        return JsonResponse({"error": "Recipe not found"}, status=404)

    return JsonResponse(
        _recipe_to_dict(recipe, is_owner=(recipe.user_id == request.user.id))
    )


def _parse_recipe_body(body):
    name = body.get("name", "").strip()
    if not name:
        raise ValueError("name is required")
    ingredients_data = body.get("ingredients", [])
    if not ingredients_data:
        raise ValueError("At least one ingredient is required")

    ingredients = []
    for item in ingredients_data:
        ing_id = item.get("ingredient_id")
        weight = item.get("weight_grams")
        if ing_id is None or weight is None:
            raise ValueError("Each ingredient must have ingredient_id and weight_grams")
        try:
            ingredients.append((int(ing_id), int(weight)))
        except (TypeError, ValueError):
            raise ValueError("ingredient_id and weight_grams must be integers")

    return {
        "name": name,
        "description": body.get("description", ""),
        "instructions": body.get("instructions", ""),
        "ingredients": ingredients,
    }


def _recipe_create(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError as e:
        return _error_response(f"Invalid JSON: {e}")

    try:
        parsed = _parse_recipe_body(body)
    except ValueError as e:
        return _error_response(str(e))

    recipe = Recipe.objects.create(
        user=request.user,
        name=parsed["name"],
        description=parsed["description"],
        instructions=parsed["instructions"],
    )

    for ing_id, weight_grams in parsed["ingredients"]:
        try:
            ingredient = Ingredient.objects.get(pk=ing_id)
        except Ingredient.DoesNotExist:
            recipe.delete()
            return _error_response(f"Ingredient id {ing_id} not found")
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=ingredient,
            weight_grams=weight_grams,
        )

    recipe.recalculate_nutrition()
    recipe.save()
    return JsonResponse(_recipe_to_dict(recipe, is_owner=True), status=201)


def _recipe_update(request, pk):
    try:
        recipe = Recipe.objects.get(pk=pk)
    except Recipe.DoesNotExist:
        return JsonResponse({"error": "Recipe not found"}, status=404)

    if recipe.user_id != request.user.id:
        return _error_response("Not allowed to edit this recipe", status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError as e:
        return _error_response(f"Invalid JSON: {e}")

    try:
        parsed = _parse_recipe_body(body)
    except ValueError as e:
        return _error_response(str(e))

    recipe.name = parsed["name"]
    recipe.description = parsed["description"]
    recipe.instructions = parsed["instructions"]
    recipe.save()

    RecipeIngredient.objects.filter(recipe=recipe).delete()
    for ing_id, weight_grams in parsed["ingredients"]:
        try:
            ingredient = Ingredient.objects.get(pk=ing_id)
        except Ingredient.DoesNotExist:
            return _error_response(f"Ingredient id {ing_id} not found")
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=ingredient,
            weight_grams=weight_grams,
        )

    recipe.recalculate_nutrition()
    recipe.save()

    return JsonResponse(
        _recipe_to_dict(
            Recipe.objects.prefetch_related("recipe_ingredients__ingredient").get(
                pk=recipe.pk
            ),
            is_owner=True,
        )
    )


def _recipe_delete(request, pk):
    try:
        recipe = Recipe.objects.get(pk=pk)
    except Recipe.DoesNotExist:
        return JsonResponse({"error": "Recipe not found"}, status=404)

    if recipe.user_id != request.user.id:
        return _error_response("Not allowed to delete this recipe", status=403)

    recipe.delete()
    return JsonResponse({"status": "ok"})


# Menu
@login_required
@require_http_methods(["GET", "PUT"])
def menu_get_or_update(request):
    if request.method == "GET":
        return _menu_get(request)
    return _menu_update(request)


def _menu_get(request):
    slots = MenuSlot.objects.filter(user=request.user).select_related("recipe")
    data = {}
    for slot in slots:
        key = f"{slot.day_of_week}-{slot.meal_type}"
        data[key] = slot.recipe_id
    for day in range(7):
        for meal in range(4):
            key = f"{day}-{meal}"
            if key not in data:
                data[key] = None
    return JsonResponse(data)


def _menu_update(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError as e:
        return _error_response(f"Invalid JSON: {e}")

    if not isinstance(body, dict):
        return _error_response("Body must be an object")

    user = request.user
    MenuSlot.objects.filter(user=user).delete()

    valid_recipe_ids = set(Recipe.objects.values_list("pk", flat=True))

    for key, recipe_id in body.items():
        if recipe_id is None:
            continue
        try:
            day_str, meal_str = key.split("-")
            day_of_week = int(day_str)
            meal_type = int(meal_str)
        except (ValueError, AttributeError):
            continue
        if day_of_week not in range(7) or meal_type not in range(4):
            continue
        if recipe_id not in valid_recipe_ids:
            continue
        MenuSlot.objects.create(
            user=user,
            day_of_week=day_of_week,
            meal_type=meal_type,
            recipe_id=recipe_id,
        )

    return JsonResponse({"status": "ok"})


# Shopping list
@login_required
@require_http_methods(["POST"])
def shopping_list(request):
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError as e:
        return _error_response(f"Invalid JSON: {e}")

    start_str = body.get("start_date")
    end_str = body.get("end_date")
    if not start_str or not end_str:
        return _error_response("start_date and end_date are required")

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        return _error_response("Invalid date format, use YYYY-MM-DD")

    if start_date > end_date:
        return _error_response("start_date must be before or equal to end_date")

    raw_people = body.get("people_count")
    if raw_people is None:
        people_count = 2
    else:
        try:
            people_count = int(raw_people)
        except (TypeError, ValueError):
            return _error_response("people_count must be an integer")
        if not (1 <= people_count <= 20):
            return _error_response("people_count must be between 1 and 20")

    user = request.user
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
            for ri in RecipeIngredient.objects.filter(recipe_id=recipe_id).select_related(
                "ingredient"
            ):
                ing_id = ri.ingredient_id
                if ing_id not in aggregated:
                    aggregated[ing_id] = {"name": ri.ingredient.name, "weight_grams": 0}
                aggregated[ing_id]["weight_grams"] += ri.weight_grams
        current += timedelta(days=1)

    result = [
        {"name": v["name"], "weight_grams": round(v["weight_grams"] * people_count)}
        for v in aggregated.values()
    ]
    result.sort(key=lambda x: x["name"])
    return JsonResponse(result, safe=False)
