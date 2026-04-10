"""Tests for MenuSlotAssignment: model, API, members endpoint, services."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from planner.models import (
    FriendRequest,
    Menu,
    MenuShare,
    MenuSlot,
    MenuSlotAssignment,
    Recipe,
)
from planner.services import duplicate_menu, get_menu_members

User = get_user_model()


class MenuSlotAssignmentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@test.com"
        )
        self.menu = Menu.objects.create(user=self.user, name="Test")
        self.recipe = Recipe.objects.create(
            user=self.user, name="Soup", description="", instructions=""
        )
        self.slot = MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe, servings=2
        )

    def test_create_assignment(self):
        a = MenuSlotAssignment.objects.create(menu_slot=self.slot, user=self.user)
        self.assertEqual(a.menu_slot, self.slot)
        self.assertEqual(a.user, self.user)

    def test_cascade_delete_with_slot(self):
        MenuSlotAssignment.objects.create(menu_slot=self.slot, user=self.user)
        self.slot.delete()
        self.assertEqual(MenuSlotAssignment.objects.count(), 0)

    def test_cascade_delete_with_menu(self):
        MenuSlotAssignment.objects.create(menu_slot=self.slot, user=self.user)
        self.menu.delete()
        self.assertEqual(MenuSlotAssignment.objects.count(), 0)

    def test_ordering_by_pk(self):
        bob = User.objects.create_user(
            username="bob", email="bob@test.com"
        )
        a1 = MenuSlotAssignment.objects.create(menu_slot=self.slot, user=self.user)
        a2 = MenuSlotAssignment.objects.create(menu_slot=self.slot, user=bob)
        assignments = list(MenuSlotAssignment.objects.all())
        self.assertEqual(assignments[0].pk, a1.pk)
        self.assertEqual(assignments[1].pk, a2.pk)


class GetMenuMembersTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@test.com"
        )
        self.carol = User.objects.create_user(
            username="carol", email="carol@test.com"
        )
        self.menu = Menu.objects.create(user=self.alice, name="Test")

    def test_owner_only(self):
        members = get_menu_members(self.menu)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]["id"], self.alice.id)
        self.assertEqual(members[0]["username"], "alice")

    def test_owner_plus_editors(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        MenuShare.objects.create(
            menu=self.menu, shared_with=self.bob, permission="edit"
        )
        members = get_menu_members(self.menu)
        self.assertEqual(len(members), 2)
        ids = {m["id"] for m in members}
        self.assertEqual(ids, {self.alice.id, self.bob.id})

    def test_read_only_user_not_included(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.carol,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        MenuShare.objects.create(
            menu=self.menu, shared_with=self.carol, permission="read"
        )
        members = get_menu_members(self.menu)
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0]["id"], self.alice.id)


class DuplicateMenuWithAssignmentsTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@test.com"
        )
        self.menu = Menu.objects.create(user=self.alice, name="Original")
        self.recipe = Recipe.objects.create(
            user=self.alice, name="Soup", description="", instructions=""
        )
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        MenuShare.objects.create(
            menu=self.menu, shared_with=self.bob, permission="edit"
        )
        self.slot = MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe, servings=2
        )
        MenuSlotAssignment.objects.create(menu_slot=self.slot, user=self.alice)
        MenuSlotAssignment.objects.create(menu_slot=self.slot, user=self.bob)

    def test_duplicate_copies_shares(self):
        new_menu = duplicate_menu(self.menu)
        self.assertEqual(new_menu.shares.count(), 1)
        share = new_menu.shares.first()
        self.assertEqual(share.shared_with, self.bob)
        self.assertEqual(share.permission, "edit")

    def test_duplicate_copies_assignments(self):
        new_menu = duplicate_menu(self.menu)
        new_slot = MenuSlot.objects.filter(menu=new_menu).first()
        assignments = list(new_slot.assignments.all())
        self.assertEqual(len(assignments), 2)
        user_ids = {a.user_id for a in assignments}
        self.assertEqual(user_ids, {self.alice.id, self.bob.id})


class ApiTestBase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )
        self.client.force_login(self.user)


class MenuMembersEndpointTests(ApiTestBase):
    def test_returns_owner(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        response = self.client.get(f"/api/menus/{menu.id}/members/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.user.id)

    def test_returns_owner_and_editors(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        bob = User.objects.create_user(
            username="bob", email="bob@test.com"
        )
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        MenuShare.objects.create(menu=menu, shared_with=bob, permission="edit")
        response = self.client.get(f"/api/menus/{menu.id}/members/")
        data = response.json()
        self.assertEqual(len(data), 2)

    def test_404_for_non_shared_user(self):
        other = User.objects.create_user(
            username="other", email="other@test.com"
        )
        menu = Menu.objects.create(user=other, name="Private")
        response = self.client.get(f"/api/menus/{menu.id}/members/")
        self.assertEqual(response.status_code, 404)

    def test_read_only_user_can_access(self):
        owner = User.objects.create_user(
            username="owner", email="owner@test.com"
        )
        menu = Menu.objects.create(user=owner, name="Shared")
        FriendRequest.objects.create(
            from_user=owner,
            to_user=self.user,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        MenuShare.objects.create(menu=menu, shared_with=self.user, permission="read")
        response = self.client.get(f"/api/menus/{menu.id}/members/")
        self.assertEqual(response.status_code, 200)


class MenuAssignmentsApiTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.menu = Menu.objects.create(user=self.user, name="Test")
        self.recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )

    def test_get_returns_assignments_array(self):
        slot = MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe, servings=2
        )
        MenuSlotAssignment.objects.create(menu_slot=slot, user=self.user)
        response = self.client.get(f"/api/menus/{self.menu.id}/")
        data = response.json()
        entry = data["0-0"][0]
        self.assertIn("assignments", entry)
        self.assertEqual(entry["assignments"], [self.user.id])

    def test_get_empty_assignments(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe, servings=1
        )
        response = self.client.get(f"/api/menus/{self.menu.id}/")
        data = response.json()
        entry = data["0-0"][0]
        self.assertEqual(entry["assignments"], [])

    def test_put_with_assignments_creates_records(self):
        body = {
            "0-0": [
                {
                    "recipe_id": self.recipe.id,
                    "servings": 2,
                    "assignments": [self.user.id],
                }
            ]
        }
        response = self.client.put(
            f"/api/menus/{self.menu.id}/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        slot = MenuSlot.objects.filter(menu=self.menu).first()
        self.assertEqual(slot.assignments.count(), 1)
        self.assertEqual(slot.assignments.first().user_id, self.user.id)

    def test_assignments_capped_at_servings_count(self):
        bob = User.objects.create_user(
            username="bob", email="bob@test.com"
        )
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        MenuShare.objects.create(menu=self.menu, shared_with=bob, permission="edit")
        body = {
            "0-0": [
                {
                    "recipe_id": self.recipe.id,
                    "servings": 1,
                    "assignments": [self.user.id, bob.id],
                }
            ]
        }
        self.client.put(
            f"/api/menus/{self.menu.id}/",
            data=body,
            content_type="application/json",
        )
        slot = MenuSlot.objects.filter(menu=self.menu).first()
        self.assertEqual(slot.assignments.count(), 1)

    def test_invalid_user_ids_silently_dropped(self):
        body = {
            "0-0": [
                {
                    "recipe_id": self.recipe.id,
                    "servings": 2,
                    "assignments": [99999, self.user.id],
                }
            ]
        }
        self.client.put(
            f"/api/menus/{self.menu.id}/",
            data=body,
            content_type="application/json",
        )
        slot = MenuSlot.objects.filter(menu=self.menu).first()
        self.assertEqual(slot.assignments.count(), 1)
        self.assertEqual(slot.assignments.first().user_id, self.user.id)

    def test_put_roundtrip_preserves_assignments(self):
        body = {
            "0-0": [
                {
                    "recipe_id": self.recipe.id,
                    "servings": 2,
                    "assignments": [self.user.id],
                }
            ]
        }
        self.client.put(
            f"/api/menus/{self.menu.id}/",
            data=body,
            content_type="application/json",
        )
        response = self.client.get(f"/api/menus/{self.menu.id}/")
        data = response.json()
        self.assertEqual(data["0-0"][0]["assignments"], [self.user.id])
