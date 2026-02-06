"""URL configuration for planner API."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from planner.views_api import (
    IngredientViewSet,
    MenuView,
    RecipeViewSet,
    ShoppingListView,
)

router = DefaultRouter()
router.register("ingredients", IngredientViewSet, basename="ingredient")
router.register("recipes", RecipeViewSet, basename="recipe")

urlpatterns = [
    path("menu/", MenuView.as_view()),
    path("shopping-list/", ShoppingListView.as_view()),
] + router.urls
