"""Django admin for planner models."""

from django.contrib import admin

from planner.models import Ingredient, MenuSlot, Recipe, RecipeIngredient


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    fields = ("ingredient", "weight_grams")
    extra = 0


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "calories", "protein", "fat", "carbs")
    list_filter = ("user",)
    search_fields = ("name",)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "total_calories",
        "total_protein",
        "total_fat",
        "total_carbs",
    )
    list_filter = ("user",)
    search_fields = ("name", "description")
    inlines = [RecipeIngredientInline]


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ("recipe", "ingredient", "weight_grams")
    list_filter = ("recipe__user",)


@admin.register(MenuSlot)
class MenuSlotAdmin(admin.ModelAdmin):
    list_display = ("user", "day_of_week", "meal_type", "recipe")
    list_filter = ("user", "day_of_week", "meal_type")
