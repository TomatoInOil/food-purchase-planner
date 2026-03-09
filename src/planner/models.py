"""Models for recipes, ingredients, and weekly menu planning."""

import secrets
import string

from django.conf import settings
from django.db import models

FRIEND_CODE_LENGTH = 8
FRIEND_CODE_ALPHABET = string.ascii_uppercase + string.digits


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


class Menu(models.Model):
    """A named weekly menu plan. Each user can have multiple menus."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menus",
    )
    name = models.CharField(max_length=200, default="Меню на неделю")
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user_id} — {self.name}"


class MenuSlot(models.Model):
    """One meal slot in a weekly menu plan."""

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

    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name="slots",
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
        ordering = ["menu", "day_of_week", "meal_type"]

    def __str__(self):
        return f"{self.get_day_of_week_display()} {self.get_meal_type_display()}"


class UserFriendCode(models.Model):
    """One-time friend code for a user. Created lazily on first API request for 'my code'."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friend_code",
    )
    code = models.CharField(max_length=20, unique=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = _generate_unique_friend_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user_id} — {self.code}"


class FriendRequest(models.Model):
    """Friend request between two users. Multiple records per pair allowed (e.g. after declined)."""

    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_DECLINED = "declined"
    STATUS_REMOVED = "removed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "pending"),
        (STATUS_ACCEPTED, "accepted"),
        (STATUS_DECLINED, "declined"),
        (STATUS_REMOVED, "removed"),
        (STATUS_CANCELLED, "cancelled"),
    ]

    EDIT_RECIPES_NONE = "none"
    EDIT_RECIPES_PENDING = "pending"
    EDIT_RECIPES_ACCEPTED = "accepted"

    EDIT_RECIPES_STATUS_CHOICES = [
        (EDIT_RECIPES_NONE, "none"),
        (EDIT_RECIPES_PENDING, "pending"),
        (EDIT_RECIPES_ACCEPTED, "accepted"),
    ]

    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_friend_requests",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_friend_requests",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    can_edit_recipes_status = models.CharField(
        max_length=20,
        choices=EDIT_RECIPES_STATUS_CHOICES,
        default=EDIT_RECIPES_NONE,
    )
    can_edit_recipes_requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="edit_recipes_requests_sent",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.from_user_id} → {self.to_user_id} ({self.status})"


def _generate_unique_friend_code():
    """Generate a unique alphanumeric code for UserFriendCode. Retries on collision."""
    while True:
        code = "".join(
            secrets.choice(FRIEND_CODE_ALPHABET) for _ in range(FRIEND_CODE_LENGTH)
        )
        if not UserFriendCode.objects.filter(code=code).exists():
            return code
