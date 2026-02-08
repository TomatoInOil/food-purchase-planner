"""URL configuration for planner API."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from planner.views_api import (
    IngredientViewSet,
    MenuView,
    RecipeViewSet,
    ShoppingListView,
)
from planner.views_friends import (
    EditRecipesRequestViewSet,
    FriendMenuView,
    FriendRemoveView,
    FriendRequestViewSet,
    FriendRevokeEditRecipesView,
    FriendSendEditRecipesRequestView,
    FriendShoppingListView,
    FriendsListView,
    MyFriendCodeView,
    SendFriendRequestView,
)

router = DefaultRouter()
router.register("ingredients", IngredientViewSet, basename="ingredient")
router.register("recipes", RecipeViewSet, basename="recipe")
router.register("friend-requests", FriendRequestViewSet, basename="friend-request")
router.register(
    "edit-recipes-requests",
    EditRecipesRequestViewSet,
    basename="edit-recipes-request",
)

urlpatterns = [
    path("menu/", MenuView.as_view()),
    path("shopping-list/", ShoppingListView.as_view()),
    path("friends/my-code/", MyFriendCodeView.as_view(), name="friends-my-code"),
    path(
        "friends/send-request/",
        SendFriendRequestView.as_view(),
        name="friends-send-request",
    ),
    path("friends/", FriendsListView.as_view(), name="friends-list"),
    path(
        "friends/<int:user_id>/remove/",
        FriendRemoveView.as_view(),
        name="friends-remove",
    ),
    path(
        "friends/<int:user_id>/send-edit-recipes-request/",
        FriendSendEditRecipesRequestView.as_view(),
        name="friends-send-edit-recipes-request",
    ),
    path(
        "friends/<int:user_id>/revoke-edit-recipes/",
        FriendRevokeEditRecipesView.as_view(),
        name="friends-revoke-edit-recipes",
    ),
    path(
        "friends/<int:user_id>/menu/",
        FriendMenuView.as_view(),
        name="friend-menu",
    ),
    path(
        "friends/<int:user_id>/shopping-list/",
        FriendShoppingListView.as_view(),
        name="friend-shopping-list",
    ),
] + router.urls
