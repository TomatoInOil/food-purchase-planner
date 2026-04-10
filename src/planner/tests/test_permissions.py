"""Tests for planner DRF permission classes."""

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from planner.models import FriendRequest, Ingredient, Recipe
from planner.permissions import (
    IsOwnerOrFriendEditorOrReadOnly,
    IsOwnerOrReadOnly,
    is_system_ingredient,
)

User = get_user_model()


class IsOwnerOrReadOnlyTests(TestCase):
    """Test IsOwnerOrReadOnly permission class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsOwnerOrReadOnly()
        self.owner = User.objects.create_user(
            username="owner", email="owner@test.com"
        )
        self.other = User.objects.create_user(
            username="other", email="other@test.com"
        )
        self.ingredient = Ingredient.objects.create(
            user=self.owner, name="Salt", calories=0
        )

    def test_safe_method_allowed_for_everyone(self):
        for method in ("get", "head", "options"):
            request = getattr(self.factory, method)("/")
            request.user = self.other
            self.assertTrue(
                self.permission.has_object_permission(
                    request, None, self.ingredient
                )
            )

    def test_write_allowed_for_owner(self):
        for method in ("post", "put", "patch", "delete"):
            request = getattr(self.factory, method)("/")
            request.user = self.owner
            self.assertTrue(
                self.permission.has_object_permission(
                    request, None, self.ingredient
                )
            )

    def test_write_denied_for_non_owner(self):
        for method in ("post", "put", "patch", "delete"):
            request = getattr(self.factory, method)("/")
            request.user = self.other
            self.assertFalse(
                self.permission.has_object_permission(
                    request, None, self.ingredient
                )
            )


class IsOwnerOrFriendEditorOrReadOnlyTests(TestCase):
    """Test IsOwnerOrFriendEditorOrReadOnly permission class."""

    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsOwnerOrFriendEditorOrReadOnly()
        self.owner = User.objects.create_user(
            username="owner", email="owner@test.com"
        )
        self.friend = User.objects.create_user(
            username="friend", email="friend@test.com"
        )
        self.stranger = User.objects.create_user(
            username="stranger", email="stranger@test.com"
        )
        self.recipe = Recipe.objects.create(
            user=self.owner, name="Soup", description="", instructions=""
        )

    def test_safe_method_allowed_for_everyone(self):
        request = self.factory.get("/")
        request.user = self.stranger
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.recipe)
        )

    def test_write_allowed_for_owner(self):
        request = self.factory.put("/")
        request.user = self.owner
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.recipe)
        )

    def test_write_allowed_for_friend_with_edit_permission(self):
        FriendRequest.objects.create(
            from_user=self.friend,
            to_user=self.owner,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        request = self.factory.put("/")
        request.user = self.friend
        self.assertTrue(
            self.permission.has_object_permission(request, None, self.recipe)
        )

    def test_write_denied_for_friend_without_edit_permission(self):
        FriendRequest.objects.create(
            from_user=self.friend,
            to_user=self.owner,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_NONE,
        )
        request = self.factory.put("/")
        request.user = self.friend
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.recipe)
        )

    def test_write_denied_for_stranger(self):
        request = self.factory.delete("/")
        request.user = self.stranger
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.recipe)
        )

    def test_write_denied_for_pending_edit_permission(self):
        FriendRequest.objects.create(
            from_user=self.friend,
            to_user=self.owner,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_PENDING,
        )
        request = self.factory.put("/")
        request.user = self.friend
        self.assertFalse(
            self.permission.has_object_permission(request, None, self.recipe)
        )


class IsSystemIngredientTests(TestCase):
    """Test is_system_ingredient helper."""

    def test_system_user_ingredient(self):
        system_user = User.objects.create_user(
            username="system", email="system@test.com"
        )
        ing = Ingredient.objects.create(user=system_user, name="Salt")
        self.assertTrue(is_system_ingredient(ing))

    def test_non_system_user_ingredient(self):
        user = User.objects.create_user(
            username="alice", email="alice@test.com"
        )
        ing = Ingredient.objects.create(user=user, name="Salt")
        self.assertFalse(is_system_ingredient(ing))
