"""Models for recipes, ingredients, and weekly menu planning."""

from django.conf import settings
from django.db import models


class Ingredient(models.Model):
    """Base ingredient with nutritional values per 100g. Owner can CRUD; others view only."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ingredients",
    )
    name = models.CharField(max_length=200)
    calories = models.FloatField(default=0)
    protein = models.FloatField(default=0)
    fat = models.FloatField(default=0)
    carbs = models.FloatField(default=0)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_ingredient_name",
            )
        ]

    def __str__(self):
        return self.name


class Recipe(models.Model):
    """Recipe with description, instructions, and ingredients. Owner can CRUD; others view only."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipes",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructions = models.TextField(blank=True)
    total_calories = models.FloatField(null=True, blank=True)
    total_protein = models.FloatField(null=True, blank=True)
    total_fat = models.FloatField(null=True, blank=True)
    total_carbs = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def recalculate_nutrition(self):
        """Compute and store total nutrition from recipe ingredients."""
        totals = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
        for ri in self.recipe_ingredients.select_related("ingredient"):
            factor = ri.weight_grams / 100
            totals["calories"] += ri.ingredient.calories * factor
            totals["protein"] += ri.ingredient.protein * factor
            totals["fat"] += ri.ingredient.fat * factor
            totals["carbs"] += ri.ingredient.carbs * factor
        self.total_calories = totals["calories"]
        self.total_protein = totals["protein"]
        self.total_fat = totals["fat"]
        self.total_carbs = totals["carbs"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.recalculate_nutrition()
        Recipe.objects.filter(pk=self.pk).update(
            total_calories=self.total_calories,
            total_protein=self.total_protein,
            total_fat=self.total_fat,
            total_carbs=self.total_carbs,
        )


class RecipeIngredient(models.Model):
    """Link between recipe and ingredient with weight in grams."""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="recipe_ingredients",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="recipe_ingredients",
    )
    weight_grams = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recipe", "ingredient"],
                name="unique_recipe_ingredient",
            )
        ]

    def __str__(self):
        return f"{self.recipe.name} — {self.ingredient.name} ({self.weight_grams}g)"


class MenuSlot(models.Model):
    """One meal slot in the weekly menu. Only owner can view and edit."""

    DAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]
    MEAL_CHOICES = [
        (0, "breakfast"),
        (1, "lunch"),
        (2, "snack"),
        (3, "dinner"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menu_slots",
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    meal_type = models.IntegerField(choices=MEAL_CHOICES)
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="menu_slots",
    )

    class Meta:
        ordering = ["user", "day_of_week", "meal_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "day_of_week", "meal_type"],
                name="unique_user_day_meal",
            )
        ]

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.get_meal_type_display()}"
