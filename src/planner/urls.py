"""URL configuration for planner API."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from planner.views_api import (
    IngredientViewSet,
    MenuDetailView,
    MenuListCreateView,
    MenuSetPrimaryView,
    MenuView,
    RecipeViewSet,
    ShoppingListView,
)
from planner.views_friends import (
    EditRecipesRequestViewSet,
    FriendMenuDetailView,
    FriendMenuListCreateView,
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
    path("menus/", MenuListCreateView.as_view(), name="menu-list-create"),
    path("menus/<int:menu_id>/", MenuDetailView.as_view(), name="menu-detail"),
    path(
        "menus/<int:menu_id>/set-primary/",
        MenuSetPrimaryView.as_view(),
        name="menu-set-primary",
    ),
    path("menu/", MenuView.as_view(), name="menu-legacy"),
    path("shopping-list/", ShoppingListView.as_view(), name="shopping-list"),
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
        "friends/<int:user_id>/menus/",
        FriendMenuListCreateView.as_view(),
        name="friend-menu-list-create",
    ),
    path(
        "friends/<int:user_id>/menus/<int:menu_id>/",
        FriendMenuDetailView.as_view(),
        name="friend-menu-detail",
    ),
    path(
        "friends/<int:user_id>/shopping-list/",
        FriendShoppingListView.as_view(),
        name="friend-shopping-list",
    ),
] + router.urls
