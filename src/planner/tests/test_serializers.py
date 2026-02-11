"""Tests for planner serializers: validation, representation, edge cases."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from planner.models import (
    FriendRequest,
    Ingredient,
    Menu,
    MenuSlot,
    Recipe,
    RecipeIngredient,
)
from planner.serializers import (
    IngredientSerializer,
    MenuItemSerializer,
    MenuSlotsSerializer,
    RecipeCreateUpdateSerializer,
    RecipeSerializer,
    ShoppingListRequestSerializer,
)

User = get_user_model()


class IngredientSerializerTests(TestCase):
    """Test IngredientSerializer validation and representation."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.request = self.factory.get("/")
        self.request.user = self.user

    def _context(self):
        return {"request": self.request}

    def test_valid_creation(self):
        data = {"name": "Salt", "calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        serializer = IngredientSerializer(data=data, context=self._context())
        self.assertTrue(serializer.is_valid())
        ing = serializer.save()
        self.assertEqual(ing.user, self.user)
        self.assertEqual(ing.name, "Salt")

    def test_blank_name_rejected(self):
        data = {"name": "", "calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        serializer = IngredientSerializer(data=data, context=self._context())
        self.assertFalse(serializer.is_valid())

    def test_whitespace_only_name_rejected(self):
        data = {"name": "   ", "calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        serializer = IngredientSerializer(data=data, context=self._context())
        self.assertFalse(serializer.is_valid())

    def test_duplicate_name_rejected(self):
        Ingredient.objects.create(user=self.user, name="Salt")
        data = {"name": "Salt", "calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        serializer = IngredientSerializer(data=data, context=self._context())
        self.assertFalse(serializer.is_valid())

    def test_name_stripped(self):
        data = {"name": "  Salt  ", "calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        serializer = IngredientSerializer(data=data, context=self._context())
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Salt")

    def test_is_owner_true_for_owner(self):
        ing = Ingredient.objects.create(user=self.user, name="Salt")
        serializer = IngredientSerializer(ing, context=self._context())
        self.assertTrue(serializer.data["is_owner"])

    def test_is_owner_false_for_other_user(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        ing = Ingredient.objects.create(user=other, name="Salt")
        serializer = IngredientSerializer(ing, context=self._context())
        self.assertFalse(serializer.data["is_owner"])

    def test_calories_must_be_number(self):
        data = {"name": "X", "calories": "abc", "protein": 0, "fat": 0, "carbs": 0}
        serializer = IngredientSerializer(data=data, context=self._context())
        self.assertFalse(serializer.is_valid())

    def test_all_fields_present_in_output(self):
        ing = Ingredient.objects.create(
            user=self.user, name="Salt", calories=0, protein=0, fat=0, carbs=0
        )
        serializer = IngredientSerializer(ing, context=self._context())
        expected_keys = {"id", "name", "calories", "protein", "fat", "carbs", "is_owner"}
        self.assertEqual(set(serializer.data.keys()), expected_keys)


class RecipeSerializerTests(TestCase):
    """Test RecipeSerializer representation and can_edit logic."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.request = self.factory.get("/")
        self.request.user = self.user
        self.ing = Ingredient.objects.create(
            user=self.user, name="Tomato", calories=18, protein=1, fat=0, carbs=4
        )
        self.recipe = Recipe.objects.create(
            user=self.user, name="Salad", description="Fresh", instructions="Mix"
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing, weight_grams=100
        )

    def _context(self, user=None, editable_owner_ids=None):
        request = self.factory.get("/")
        request.user = user or self.user
        ctx = {"request": request}
        if editable_owner_ids is not None:
            ctx["editable_owner_ids"] = editable_owner_ids
        return ctx

    def test_representation_fields(self):
        serializer = RecipeSerializer(self.recipe, context=self._context())
        data = serializer.data
        expected_keys = {
            "id", "name", "description", "instructions",
            "total_calories", "total_protein", "total_fat", "total_carbs",
            "is_owner", "can_edit", "ingredients", "author_username",
        }
        self.assertEqual(set(data.keys()), expected_keys)

    def test_is_owner_true_for_owner(self):
        serializer = RecipeSerializer(self.recipe, context=self._context())
        self.assertTrue(serializer.data["is_owner"])

    def test_is_owner_false_for_other(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        serializer = RecipeSerializer(self.recipe, context=self._context(user=other))
        self.assertFalse(serializer.data["is_owner"])

    def test_can_edit_true_for_owner(self):
        serializer = RecipeSerializer(self.recipe, context=self._context())
        self.assertTrue(serializer.data["can_edit"])

    def test_can_edit_true_for_friend_editor_via_context(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        ctx = self._context(user=other, editable_owner_ids={self.user.id})
        serializer = RecipeSerializer(self.recipe, context=ctx)
        self.assertTrue(serializer.data["can_edit"])

    def test_can_edit_false_for_non_friend(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        ctx = self._context(user=other, editable_owner_ids=set())
        serializer = RecipeSerializer(self.recipe, context=ctx)
        self.assertFalse(serializer.data["can_edit"])

    def test_can_edit_fallback_to_db_check_without_context(self):
        """When editable_owner_ids is not in context, falls back to DB check."""
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        FriendRequest.objects.create(
            from_user=other,
            to_user=self.user,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        ctx = self._context(user=other)
        serializer = RecipeSerializer(self.recipe, context=ctx)
        self.assertTrue(serializer.data["can_edit"])

    def test_author_username(self):
        serializer = RecipeSerializer(self.recipe, context=self._context())
        self.assertEqual(serializer.data["author_username"], "alice")

    def test_ingredients_list_structure(self):
        serializer = RecipeSerializer(self.recipe, context=self._context())
        ingredients = serializer.data["ingredients"]
        self.assertEqual(len(ingredients), 1)
        self.assertEqual(ingredients[0]["ingredient_id"], self.ing.id)
        self.assertEqual(ingredients[0]["ingredient_name"], "Tomato")
        self.assertEqual(ingredients[0]["weight_grams"], 100)

    def test_nutrition_defaults_to_zero(self):
        recipe = Recipe.objects.create(
            user=self.user, name="Empty", description="", instructions=""
        )
        serializer = RecipeSerializer(recipe, context=self._context())
        data = serializer.data
        self.assertEqual(data["total_calories"], 0)
        self.assertEqual(data["total_protein"], 0)
        self.assertEqual(data["total_fat"], 0)
        self.assertEqual(data["total_carbs"], 0)

    def test_empty_description_serialized_as_empty_string(self):
        """Recipes with blank description/instructions serialize to empty string."""
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        serializer = RecipeSerializer(recipe, context=self._context())
        self.assertEqual(serializer.data["description"], "")
        self.assertEqual(serializer.data["instructions"], "")


class RecipeCreateUpdateSerializerTests(TestCase):
    """Test RecipeCreateUpdateSerializer write operations."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.request = self.factory.post("/")
        self.request.user = self.user
        self.ing = Ingredient.objects.create(
            user=self.user, name="Tomato", calories=18, protein=1, fat=0, carbs=4
        )

    def _context(self):
        return {"request": self.request}

    def test_create_recipe_with_ingredients(self):
        data = {
            "name": "Salad",
            "description": "Fresh",
            "instructions": "Mix",
            "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 200}],
        }
        serializer = RecipeCreateUpdateSerializer(data=data, context=self._context())
        self.assertTrue(serializer.is_valid(), serializer.errors)
        recipe = serializer.save()
        self.assertEqual(recipe.name, "Salad")
        self.assertEqual(recipe.recipe_ingredients.count(), 1)

    def test_create_recipe_empty_name_rejected(self):
        data = {
            "name": "",
            "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 100}],
        }
        serializer = RecipeCreateUpdateSerializer(data=data, context=self._context())
        self.assertFalse(serializer.is_valid())

    def test_create_recipe_empty_ingredients_rejected(self):
        data = {"name": "X", "ingredients": []}
        serializer = RecipeCreateUpdateSerializer(data=data, context=self._context())
        self.assertFalse(serializer.is_valid())

    def test_create_recipe_invalid_ingredient_id_rejected(self):
        data = {
            "name": "X",
            "ingredients": [{"ingredient_id": 99999, "weight_grams": 100}],
        }
        serializer = RecipeCreateUpdateSerializer(data=data, context=self._context())
        self.assertTrue(serializer.is_valid())
        with self.assertRaises(Exception):
            serializer.save()

    def test_create_recipe_weight_grams_min_value(self):
        data = {
            "name": "X",
            "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 0}],
        }
        serializer = RecipeCreateUpdateSerializer(data=data, context=self._context())
        self.assertFalse(serializer.is_valid())

    def test_update_recipe_replaces_ingredients(self):
        recipe = Recipe.objects.create(
            user=self.user, name="Old", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing, weight_grams=100
        )
        ing2 = Ingredient.objects.create(
            user=self.user, name="Cheese", calories=300
        )
        data = {
            "name": "New",
            "description": "d",
            "instructions": "i",
            "ingredients": [{"ingredient_id": ing2.id, "weight_grams": 50}],
        }
        serializer = RecipeCreateUpdateSerializer(
            instance=recipe, data=data, context=self._context()
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.name, "New")
        self.assertEqual(updated.recipe_ingredients.count(), 1)
        self.assertEqual(updated.recipe_ingredients.first().ingredient_id, ing2.id)


class MenuItemSerializerTests(TestCase):
    """Test MenuItemSerializer fields."""

    def test_serializes_menu_fields(self):
        user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        menu = Menu.objects.create(user=user, name="Weekly", is_primary=True)
        serializer = MenuItemSerializer(menu)
        data = serializer.data
        self.assertEqual(data["name"], "Weekly")
        self.assertTrue(data["is_primary"])
        self.assertIn("id", data)
        self.assertIn("created_at", data)


class MenuSlotsSerializerTests(TestCase):
    """Test MenuSlotsSerializer representation."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.menu = Menu.objects.create(user=self.user, name="Test")

    def test_empty_menu_all_null_slots(self):
        serializer = MenuSlotsSerializer(instance=self.menu)
        data = serializer.data
        self.assertEqual(len(data), 28)
        for day in range(7):
            for meal in range(4):
                self.assertIsNone(data[f"{day}-{meal}"])

    def test_filled_slot_returns_recipe_id(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=3, meal_type=2, recipe=recipe
        )
        serializer = MenuSlotsSerializer(instance=self.menu)
        self.assertEqual(serializer.data["3-2"], recipe.id)


class ShoppingListRequestSerializerTests(TestCase):
    """Test ShoppingListRequestSerializer validation."""

    def test_valid_data(self):
        data = {
            "start_date": "2026-01-01",
            "end_date": "2026-01-07",
            "people_count": 2,
        }
        serializer = ShoppingListRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["start_date"], date(2026, 1, 1))
        self.assertEqual(serializer.validated_data["end_date"], date(2026, 1, 7))

    def test_invalid_date_format(self):
        data = {"start_date": "01-01-2026", "end_date": "07-01-2026"}
        serializer = ShoppingListRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_start_after_end_rejected(self):
        data = {"start_date": "2026-01-07", "end_date": "2026-01-01"}
        serializer = ShoppingListRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_people_count_default(self):
        data = {"start_date": "2026-01-01", "end_date": "2026-01-07"}
        serializer = ShoppingListRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["people_count"], 2)

    def test_people_count_min_value(self):
        data = {
            "start_date": "2026-01-01",
            "end_date": "2026-01-07",
            "people_count": 0,
        }
        serializer = ShoppingListRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_people_count_max_value(self):
        data = {
            "start_date": "2026-01-01",
            "end_date": "2026-01-07",
            "people_count": 21,
        }
        serializer = ShoppingListRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_missing_start_date(self):
        data = {"end_date": "2026-01-07"}
        serializer = ShoppingListRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_missing_end_date(self):
        data = {"start_date": "2026-01-01"}
        serializer = ShoppingListRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
