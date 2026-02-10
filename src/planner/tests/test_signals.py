"""Tests for planner signals: auto-recalculate nutrition on RecipeIngredient changes."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from planner.models import Ingredient, Recipe, RecipeIngredient

User = get_user_model()


class RecalculateNutritionSignalTests(TestCase):
    """Test that post_save and post_delete signals update recipe nutrition."""

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
        self.recipe = Recipe.objects.create(
            user=self.user, name="Soup", description="", instructions=""
        )

    def test_nutrition_updated_on_ingredient_add(self):
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_a, weight_grams=100
        )
        self.recipe.refresh_from_db()
        self.assertAlmostEqual(self.recipe.total_calories, 100.0)
        self.assertAlmostEqual(self.recipe.total_protein, 10.0)

    def test_nutrition_updated_on_second_ingredient_add(self):
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_a, weight_grams=100
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_b, weight_grams=50
        )
        self.recipe.refresh_from_db()
        self.assertAlmostEqual(self.recipe.total_calories, 200.0)
        self.assertAlmostEqual(self.recipe.total_protein, 20.0)

    def test_nutrition_updated_on_ingredient_delete(self):
        ri_a = RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_a, weight_grams=100
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_b, weight_grams=50
        )
        ri_a.delete()
        self.recipe.refresh_from_db()
        self.assertAlmostEqual(self.recipe.total_calories, 100.0)
        self.assertAlmostEqual(self.recipe.total_protein, 10.0)

    def test_nutrition_zeroed_when_all_ingredients_removed(self):
        ri = RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_a, weight_grams=100
        )
        ri.delete()
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.total_calories, 0)
        self.assertEqual(self.recipe.total_protein, 0)

    def test_nutrition_updated_on_weight_change(self):
        ri = RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_a, weight_grams=100
        )
        self.recipe.refresh_from_db()
        self.assertAlmostEqual(self.recipe.total_calories, 100.0)

        ri.weight_grams = 200
        ri.save()
        self.recipe.refresh_from_db()
        self.assertAlmostEqual(self.recipe.total_calories, 200.0)
