"""Django admin for planner models."""

from django.contrib import admin

from planner.models import (
    Ingredient,
    Menu,
    MenuSlot,
    Recipe,
    RecipeCategory,
    RecipeIngredient,
)


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    fields = ("ingredient", "weight_grams")
    extra = 0


class MenuSlotInline(admin.TabularInline):
    model = MenuSlot
    fields = ("day_of_week", "meal_type", "recipe")
    extra = 0


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "calories", "protein", "fat", "carbs")
    list_filter = ("user",)
    search_fields = ("name",)


@admin.register(RecipeCategory)
class RecipeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user")
    list_filter = ("user",)
    search_fields = ("name",)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "category",
        "total_calories",
        "total_protein",
        "total_fat",
        "total_carbs",
    )
    list_filter = ("user", "category")
    search_fields = ("name", "description")
    inlines = [RecipeIngredientInline]


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ("recipe", "ingredient", "weight_grams")
    list_filter = ("recipe__user",)


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    list_filter = ("user",)
    search_fields = ("name",)
    inlines = [MenuSlotInline]


@admin.register(MenuSlot)
class MenuSlotAdmin(admin.ModelAdmin):
    list_display = ("menu", "day_of_week", "meal_type", "recipe")
    list_filter = ("menu__user", "day_of_week", "meal_type")
