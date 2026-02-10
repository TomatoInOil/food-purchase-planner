"""Tests for planner models: constraints, __str__, save logic, nutrition calculation."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from planner.models import (
    FRIEND_CODE_ALPHABET,
    FRIEND_CODE_LENGTH,
    FriendRequest,
    Ingredient,
    Menu,
    MenuSlot,
    Recipe,
    RecipeIngredient,
    UserFriendCode,
    _generate_unique_friend_code,
)

User = get_user_model()


class IngredientModelTests(TestCase):
    """Test Ingredient model behaviour."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )

    def test_str_returns_name(self):
        ing = Ingredient.objects.create(user=self.user, name="Tomato", calories=18)
        self.assertEqual(str(ing), "Tomato")

    def test_default_nutrition_values_are_zero(self):
        ing = Ingredient.objects.create(user=self.user, name="Water")
        self.assertEqual(ing.calories, 0)
        self.assertEqual(ing.protein, 0)
        self.assertEqual(ing.fat, 0)
        self.assertEqual(ing.carbs, 0)

    def test_ordering_by_name(self):
        Ingredient.objects.create(user=self.user, name="Banana")
        Ingredient.objects.create(user=self.user, name="Apple")
        names = list(Ingredient.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Apple", "Banana"])

    def test_unique_user_ingredient_name_constraint(self):
        Ingredient.objects.create(user=self.user, name="Salt")
        with self.assertRaises(IntegrityError):
            Ingredient.objects.create(user=self.user, name="Salt")

    def test_same_name_different_users_allowed(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        Ingredient.objects.create(user=self.user, name="Salt")
        ing2 = Ingredient.objects.create(user=other, name="Salt")
        self.assertEqual(ing2.name, "Salt")


class RecipeModelTests(TestCase):
    """Test Recipe model: nutrition calculation and save logic."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.ing_a = Ingredient.objects.create(
            user=self.user, name="A", calories=100, protein=10, fat=5, carbs=20
        )
        self.ing_b = Ingredient.objects.create(
            user=self.user, name="B", calories=200, protein=20, fat=10, carbs=40
        )

    def test_str_returns_name(self):
        recipe = Recipe.objects.create(
            user=self.user, name="Soup", description="", instructions=""
        )
        self.assertEqual(str(recipe), "Soup")

    def test_ordering_by_name(self):
        Recipe.objects.create(
            user=self.user, name="Zucchini Soup", description="", instructions=""
        )
        Recipe.objects.create(
            user=self.user, name="Apple Pie", description="", instructions=""
        )
        names = list(Recipe.objects.values_list("name", flat=True))
        self.assertEqual(names, ["Apple Pie", "Zucchini Soup"])

    def test_recalculate_nutrition_single_ingredient(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing_a, weight_grams=200
        )
        recipe.recalculate_nutrition()
        self.assertAlmostEqual(recipe.total_calories, 200.0)
        self.assertAlmostEqual(recipe.total_protein, 20.0)
        self.assertAlmostEqual(recipe.total_fat, 10.0)
        self.assertAlmostEqual(recipe.total_carbs, 40.0)

    def test_recalculate_nutrition_multiple_ingredients(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing_a, weight_grams=100
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing_b, weight_grams=50
        )
        recipe.recalculate_nutrition()
        self.assertAlmostEqual(recipe.total_calories, 100.0 + 100.0)
        self.assertAlmostEqual(recipe.total_protein, 10.0 + 10.0)
        self.assertAlmostEqual(recipe.total_fat, 5.0 + 5.0)
        self.assertAlmostEqual(recipe.total_carbs, 20.0 + 20.0)

    def test_recalculate_nutrition_no_ingredients(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        recipe.recalculate_nutrition()
        self.assertEqual(recipe.total_calories, 0)
        self.assertEqual(recipe.total_protein, 0)
        self.assertEqual(recipe.total_fat, 0)
        self.assertEqual(recipe.total_carbs, 0)

    def test_save_triggers_nutrition_recalculation(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing_a, weight_grams=100
        )
        recipe.save()
        recipe.refresh_from_db()
        self.assertAlmostEqual(recipe.total_calories, 100.0)

    def test_save_persists_nutrition_to_db(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing_a, weight_grams=150
        )
        recipe.save()
        db_recipe = Recipe.objects.get(pk=recipe.pk)
        self.assertAlmostEqual(db_recipe.total_calories, 150.0)
        self.assertAlmostEqual(db_recipe.total_protein, 15.0)


class RecipeIngredientModelTests(TestCase):
    """Test RecipeIngredient constraints and __str__."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.ing = Ingredient.objects.create(user=self.user, name="Flour", calories=364)
        self.recipe = Recipe.objects.create(
            user=self.user, name="Bread", description="", instructions=""
        )

    def test_str_format(self):
        ri = RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing, weight_grams=500
        )
        self.assertEqual(str(ri), "Bread — Flour (500g)")

    def test_unique_recipe_ingredient_constraint(self):
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing, weight_grams=100
        )
        with self.assertRaises(IntegrityError):
            RecipeIngredient.objects.create(
                recipe=self.recipe, ingredient=self.ing, weight_grams=200
            )

    def test_ingredient_protect_on_delete(self):
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing, weight_grams=100
        )
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.ing.delete()

    def test_recipe_cascade_deletes_recipe_ingredients(self):
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing, weight_grams=100
        )
        recipe_id = self.recipe.pk
        self.recipe.delete()
        self.assertFalse(RecipeIngredient.objects.filter(recipe_id=recipe_id).exists())


class MenuModelTests(TestCase):
    """Test Menu model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )

    def test_str_format(self):
        menu = Menu.objects.create(user=self.user, name="Weekly Plan")
        self.assertIn("Weekly Plan", str(menu))

    def test_default_name(self):
        menu = Menu.objects.create(user=self.user)
        self.assertEqual(menu.name, "Меню на неделю")

    def test_ordering_by_created_at(self):
        m1 = Menu.objects.create(user=self.user, name="First")
        m2 = Menu.objects.create(user=self.user, name="Second")
        menus = list(Menu.objects.filter(user=self.user))
        self.assertEqual(menus[0].pk, m1.pk)
        self.assertEqual(menus[1].pk, m2.pk)

    def test_is_primary_default_false(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        self.assertFalse(menu.is_primary)


class MenuSlotModelTests(TestCase):
    """Test MenuSlot model constraints and __str__."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.menu = Menu.objects.create(user=self.user, name="Test")
        self.recipe = Recipe.objects.create(
            user=self.user, name="Soup", description="", instructions=""
        )

    def test_str_format(self):
        slot = MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=1, recipe=self.recipe
        )
        self.assertEqual(str(slot), "Monday lunch")

    def test_unique_menu_day_meal_constraint(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe
        )
        with self.assertRaises(IntegrityError):
            MenuSlot.objects.create(
                menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe
            )

    def test_slot_with_null_recipe_allowed(self):
        slot = MenuSlot.objects.create(
            menu=self.menu, day_of_week=3, meal_type=2, recipe=None
        )
        self.assertIsNone(slot.recipe)

    def test_ordering_by_menu_day_meal(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=2, meal_type=0, recipe=self.recipe
        )
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=1, recipe=self.recipe
        )
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe
        )
        slots = list(MenuSlot.objects.filter(menu=self.menu))
        days_meals = [(s.day_of_week, s.meal_type) for s in slots]
        self.assertEqual(days_meals, [(0, 0), (0, 1), (2, 0)])

    def test_cascade_on_menu_delete(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe
        )
        menu_id = self.menu.pk
        self.menu.delete()
        self.assertFalse(MenuSlot.objects.filter(menu_id=menu_id).exists())


class UserFriendCodeModelTests(TestCase):
    """Test UserFriendCode: auto-generation, uniqueness."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )

    def test_save_generates_code_when_empty(self):
        code_obj = UserFriendCode(user=self.user)
        code_obj.save()
        self.assertTrue(code_obj.code)
        self.assertEqual(len(code_obj.code), FRIEND_CODE_LENGTH)

    def test_generated_code_uses_valid_alphabet(self):
        code_obj = UserFriendCode(user=self.user)
        code_obj.save()
        for char in code_obj.code:
            self.assertIn(char, FRIEND_CODE_ALPHABET)

    def test_save_preserves_explicit_code(self):
        code_obj = UserFriendCode(user=self.user, code="CUSTOM99")
        code_obj.save()
        self.assertEqual(code_obj.code, "CUSTOM99")

    def test_str_format(self):
        code_obj = UserFriendCode.objects.create(user=self.user, code="ABC12345")
        self.assertIn("ABC12345", str(code_obj))

    def test_one_to_one_with_user(self):
        UserFriendCode.objects.create(user=self.user, code="CODE1111")
        with self.assertRaises(IntegrityError):
            UserFriendCode.objects.create(user=self.user, code="CODE2222")

    def test_code_unique(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        UserFriendCode.objects.create(user=self.user, code="SAMECODE")
        with self.assertRaises(IntegrityError):
            UserFriendCode.objects.create(user=other, code="SAMECODE")


class GenerateUniqueFriendCodeTests(TestCase):
    """Test _generate_unique_friend_code helper."""

    def test_returns_valid_code(self):
        code = _generate_unique_friend_code()
        self.assertEqual(len(code), FRIEND_CODE_LENGTH)
        for char in code:
            self.assertIn(char, FRIEND_CODE_ALPHABET)

    def test_codes_are_unique(self):
        codes = {_generate_unique_friend_code() for _ in range(20)}
        self.assertEqual(len(codes), 20)


class FriendRequestModelTests(TestCase):
    """Test FriendRequest model."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )

    def test_str_format(self):
        fr = FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
        )
        result = str(fr)
        self.assertIn("pending", result)

    def test_default_edit_recipes_status_is_none(self):
        fr = FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
        )
        self.assertEqual(fr.can_edit_recipes_status, FriendRequest.EDIT_RECIPES_NONE)

    def test_ordering_by_created_at_desc(self):
        fr1 = FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
        )
        fr2 = FriendRequest.objects.create(
            from_user=self.bob,
            to_user=self.alice,
            status=FriendRequest.STATUS_PENDING,
        )
        requests = list(FriendRequest.objects.all())
        self.assertEqual(requests[0].pk, fr2.pk)
        self.assertEqual(requests[1].pk, fr1.pk)

    def test_cascade_on_user_delete(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        self.alice.delete()
        self.assertEqual(FriendRequest.objects.count(), 0)

    def test_can_edit_recipes_requested_by_set_null_on_delete(self):
        carol = User.objects.create_user(
            username="carol", password="pass", email="carol@test.com"
        )
        fr = FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_PENDING,
            can_edit_recipes_requested_by=carol,
        )
        carol.delete()
        fr.refresh_from_db()
        self.assertIsNone(fr.can_edit_recipes_requested_by)

    def test_status_choices_values(self):
        self.assertEqual(FriendRequest.STATUS_PENDING, "pending")
        self.assertEqual(FriendRequest.STATUS_ACCEPTED, "accepted")
        self.assertEqual(FriendRequest.STATUS_DECLINED, "declined")
        self.assertEqual(FriendRequest.STATUS_REMOVED, "removed")
        self.assertEqual(FriendRequest.STATUS_CANCELLED, "cancelled")

    def test_edit_recipes_status_choices_values(self):
        self.assertEqual(FriendRequest.EDIT_RECIPES_NONE, "none")
        self.assertEqual(FriendRequest.EDIT_RECIPES_PENDING, "pending")
        self.assertEqual(FriendRequest.EDIT_RECIPES_ACCEPTED, "accepted")
