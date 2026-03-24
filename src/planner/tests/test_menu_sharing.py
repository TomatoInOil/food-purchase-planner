"""Tests for menu sharing, active menu, and servings-based shopping list."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from planner.models import (
    FriendRequest,
    Ingredient,
    Menu,
    MenuShare,
    MenuSlot,
    Recipe,
    RecipeIngredient,
)
from planner.services import (
    calculate_shopping_list,
    get_active_menu,
    revoke_all_shares_between,
    revoke_menu_share,
    set_active_menu,
    share_menu,
)

User = get_user_model()


class MenuShareModelTests(TestCase):
    """Test MenuShare model constraints and sharing service."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        self.menu = Menu.objects.create(user=self.alice, name="Alice Menu")
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )

    def test_share_menu_creates_share(self):
        share = share_menu(self.menu, self.bob, "read")
        self.assertEqual(share.menu, self.menu)
        self.assertEqual(share.shared_with, self.bob)
        self.assertEqual(share.permission, "read")

    def test_share_menu_unique_constraint(self):
        share_menu(self.menu, self.bob, "read")
        share = share_menu(self.menu, self.bob, "edit")
        self.assertEqual(MenuShare.objects.filter(menu=self.menu).count(), 1)
        self.assertEqual(share.permission, "edit")

    def test_share_menu_not_friend_raises(self):
        stranger = User.objects.create_user(
            username="stranger", password="pass", email="stranger@test.com"
        )
        with self.assertRaises(ValidationError):
            share_menu(self.menu, stranger, "read")

    def test_share_menu_self_raises(self):
        with self.assertRaises(ValidationError):
            share_menu(self.menu, self.alice, "read")


class UserActiveMenuTests(TestCase):
    """Test get_active_menu and set_active_menu services."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        self.menu_a = Menu.objects.create(user=self.alice, name="Menu A")
        self.menu_b = Menu.objects.create(user=self.alice, name="Menu B")
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )

    def test_get_active_menu_fallback_to_first(self):
        menu = get_active_menu(self.alice)
        self.assertEqual(menu.pk, self.menu_a.pk)

    def test_set_and_get_active_menu(self):
        set_active_menu(self.alice, self.menu_b)
        menu = get_active_menu(self.alice)
        self.assertEqual(menu.pk, self.menu_b.pk)

    def test_set_active_shared_menu(self):
        share_menu(self.menu_a, self.bob, "read")
        set_active_menu(self.bob, self.menu_a)
        menu = get_active_menu(self.bob)
        self.assertEqual(menu.pk, self.menu_a.pk)

    def test_set_active_inaccessible_raises(self):
        with self.assertRaises(ValidationError):
            set_active_menu(self.bob, self.menu_a)

    def test_revoke_resets_active_menu(self):
        share = share_menu(self.menu_a, self.bob, "read")
        set_active_menu(self.bob, self.menu_a)
        revoke_menu_share(share)
        menu = get_active_menu(self.bob)
        self.assertNotEqual(menu.pk, self.menu_a.pk)

    def test_get_active_falls_back_when_share_revoked(self):
        share = share_menu(self.menu_a, self.bob, "read")
        set_active_menu(self.bob, self.menu_a)
        share.delete()
        menu = get_active_menu(self.bob)
        self.assertNotEqual(menu.pk, self.menu_a.pk)


class ShoppingListServingsTests(TestCase):
    """Test calculate_shopping_list with per-slot servings × people_count."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.menu = Menu.objects.create(user=self.user, name="Test")
        self.ing = Ingredient.objects.create(user=self.user, name="Tomato", calories=18)
        self.recipe = Recipe.objects.create(
            user=self.user, name="Salad", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing, weight_grams=100
        )

    def test_servings_multiplied(self):
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=self.recipe,
            servings=3,
        )
        result = calculate_shopping_list(self.menu, today, today, people_count=1)
        tomato = next(i for i in result if i["name"] == "Tomato")
        self.assertEqual(tomato["weight_grams"], 300)

    def test_servings_times_people_count(self):
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=self.recipe,
            servings=2,
        )
        result = calculate_shopping_list(self.menu, today, today, people_count=3)
        tomato = next(i for i in result if i["name"] == "Tomato")
        self.assertEqual(tomato["weight_grams"], 600)


class MenuShareAPITests(TestCase):
    """Test menu sharing API endpoints."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        self.menu = Menu.objects.create(user=self.alice, name="Alice Menu")
        self.client_alice = APIClient()
        self.client_alice.force_authenticate(user=self.alice)
        self.client_bob = APIClient()
        self.client_bob.force_authenticate(user=self.bob)

    def test_create_share(self):
        resp = self.client_alice.post(
            f"/api/menus/{self.menu.id}/shares/",
            {"user_id": self.bob.id, "permission": "read"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["shared_with"]["id"], self.bob.id)

    def test_list_shares(self):
        share_menu(self.menu, self.bob, "read")
        resp = self.client_alice.get(f"/api/menus/{self.menu.id}/shares/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_non_owner_cannot_create_share(self):
        resp = self.client_bob.post(
            f"/api/menus/{self.menu.id}/shares/",
            {"user_id": self.alice.id, "permission": "read"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_non_friend_share_rejected(self):
        stranger = User.objects.create_user(
            username="stranger", password="pass", email="stranger@test.com"
        )
        resp = self.client_alice.post(
            f"/api/menus/{self.menu.id}/shares/",
            {"user_id": stranger.id, "permission": "read"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_share_by_owner(self):
        share = share_menu(self.menu, self.bob, "read")
        resp = self.client_alice.delete(f"/api/menus/{self.menu.id}/shares/{share.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(MenuShare.objects.filter(pk=share.id).exists())

    def test_delete_share_by_shared_user(self):
        share = share_menu(self.menu, self.bob, "read")
        resp = self.client_bob.delete(f"/api/menus/{self.menu.id}/shares/{share.id}/")
        self.assertEqual(resp.status_code, 200)


class MenuDetailAccessTests(TestCase):
    """Test GET/PUT on menu detail respects sharing permissions."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        self.menu = Menu.objects.create(user=self.alice, name="Alice Menu")
        self.client_bob = APIClient()
        self.client_bob.force_authenticate(user=self.bob)

    def test_no_share_returns_404(self):
        resp = self.client_bob.get(f"/api/menus/{self.menu.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_read_share_allows_get(self):
        share_menu(self.menu, self.bob, "read")
        resp = self.client_bob.get(f"/api/menus/{self.menu.id}/")
        self.assertEqual(resp.status_code, 200)

    def test_read_share_denies_put(self):
        share_menu(self.menu, self.bob, "read")
        resp = self.client_bob.put(
            f"/api/menus/{self.menu.id}/",
            {"0-0": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_edit_share_allows_put(self):
        share_menu(self.menu, self.bob, "edit")
        resp = self.client_bob.put(
            f"/api/menus/{self.menu.id}/",
            {"0-0": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_shared_menus_appear_in_list(self):
        share_menu(self.menu, self.bob, "read")
        resp = self.client_bob.get("/api/menus/")
        self.assertEqual(resp.status_code, 200)
        ids = [m["id"] for m in resp.data]
        self.assertIn(self.menu.id, ids)


class RevokeAllSharesBetweenTests(TestCase):
    """Test that removing a friend revokes all menu shares between them."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        self.menu_a = Menu.objects.create(user=self.alice, name="A Menu")
        self.menu_b = Menu.objects.create(user=self.bob, name="B Menu")
        share_menu(self.menu_a, self.bob, "edit")
        share_menu(self.menu_b, self.alice, "read")

    def test_revoke_all_removes_both_directions(self):
        self.assertEqual(MenuShare.objects.count(), 2)
        revoke_all_shares_between(self.alice, self.bob)
        self.assertEqual(MenuShare.objects.count(), 0)
