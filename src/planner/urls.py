"""URL configuration for planner API."""

from django.urls import path

from planner.api import (
    ingredient_delete,
    ingredient_list_or_create,
    menu_get_or_update,
    recipe_detail_update_delete,
    recipe_list_or_create,
    shopping_list,
)

urlpatterns = [
    path("ingredients/", ingredient_list_or_create),
    path("ingredients/<int:pk>/", ingredient_delete),
    path("recipes/", recipe_list_or_create),
    path("recipes/<int:pk>/", recipe_detail_update_delete),
    path("menu/", menu_get_or_update),
    path("shopping-list/", shopping_list),
]
