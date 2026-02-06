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
    FriendRemoveView,
    FriendRequestViewSet,
    FriendsListView,
    MyFriendCodeView,
    SendFriendRequestView,
)

router = DefaultRouter()
router.register("ingredients", IngredientViewSet, basename="ingredient")
router.register("recipes", RecipeViewSet, basename="recipe")
router.register("friend-requests", FriendRequestViewSet, basename="friend-request")

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
] + router.urls
