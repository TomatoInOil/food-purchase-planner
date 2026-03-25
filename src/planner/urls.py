"""URL configuration for planner API."""

from django.urls import path
from rest_framework.routers import DefaultRouter

from planner.views_api import (
    IngredientImportFromContentView,
    IngredientViewSet,
    MenuDetailView,
    MenuDuplicateView,
    MenuListCreateView,
    MenuMembersView,
    MenuSetActiveView,
    MenuShareDetailView,
    MenuShareListCreateView,
    MenuView,
    RecipeCategoryViewSet,
    RecipeViewSet,
    ShoppingListView,
)
from planner.views_friends import (
    EditRecipesRequestViewSet,
    FriendRemoveView,
    FriendRequestViewSet,
    FriendRevokeEditRecipesView,
    FriendSendEditRecipesRequestView,
    FriendsListView,
    MyFriendCodeView,
    SendFriendRequestView,
)
from planner.views_telegram import (
    TelegramGenerateLinkView,
    TelegramStatusView,
)

router = DefaultRouter()
router.register("ingredients", IngredientViewSet, basename="ingredient")
router.register("recipes", RecipeViewSet, basename="recipe")
router.register("recipe-categories", RecipeCategoryViewSet, basename="recipe-category")
router.register("friend-requests", FriendRequestViewSet, basename="friend-request")
router.register(
    "edit-recipes-requests",
    EditRecipesRequestViewSet,
    basename="edit-recipes-request",
)

urlpatterns = [
    path(
        "ingredients/import-page-content/",
        IngredientImportFromContentView.as_view(),
        name="ingredient-import-page-content",
    ),
    path("menus/", MenuListCreateView.as_view(), name="menu-list-create"),
    path("menus/<int:menu_id>/", MenuDetailView.as_view(), name="menu-detail"),
    path(
        "menus/<int:menu_id>/set-active/",
        MenuSetActiveView.as_view(),
        name="menu-set-active",
    ),
    path(
        "menus/<int:menu_id>/duplicate/",
        MenuDuplicateView.as_view(),
        name="menu-duplicate",
    ),
    path(
        "menus/<int:menu_id>/members/",
        MenuMembersView.as_view(),
        name="menu-members",
    ),
    path(
        "menus/<int:menu_id>/shares/",
        MenuShareListCreateView.as_view(),
        name="menu-share-list-create",
    ),
    path(
        "menus/<int:menu_id>/shares/<int:share_id>/",
        MenuShareDetailView.as_view(),
        name="menu-share-detail",
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
        "telegram/generate-link/",
        TelegramGenerateLinkView.as_view(),
        name="telegram-generate-link",
    ),
    path(
        "telegram/status/",
        TelegramStatusView.as_view(),
        name="telegram-status",
    ),
] + router.urls
