"""API edge-case tests: authentication, authorization, boundary conditions, error handling."""

import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from planner.models import (
    FriendRequest,
    Ingredient,
    Menu,
    MenuSlot,
    Recipe,
    RecipeIngredient,
    UserFriendCode,
)

User = get_user_model()


class AuthenticationRequiredTests(TestCase):
    """Verify that unauthenticated requests are rejected across all endpoints."""

    def setUp(self):
        self.client = Client()

    def test_ingredient_list_readable_without_auth(self):
        """Ingredient list uses IsOwnerOrReadOnly — GET is public."""
        response = self.client.get("/api/ingredients/")
        self.assertEqual(response.status_code, 200)

    def test_recipe_list_readable_without_auth(self):
        """Recipe list uses IsOwnerOrFriendEditorOrReadOnly — GET is public."""
        response = self.client.get("/api/recipes/")
        self.assertEqual(response.status_code, 200)

    def test_menu_requires_auth(self):
        response = self.client.get("/api/menu/")
        self.assertIn(response.status_code, [401, 403])

    def test_menus_list_requires_auth(self):
        response = self.client.get("/api/menus/")
        self.assertIn(response.status_code, [401, 403])

    def test_shopping_list_requires_auth(self):
        response = self.client.post(
            "/api/shopping-list/",
            data=json.dumps({"start_date": "2026-01-01", "end_date": "2026-01-07"}),
            content_type="application/json",
        )
        self.assertIn(response.status_code, [401, 403])

    def test_friends_my_code_requires_auth(self):
        response = self.client.get("/api/friends/my-code/")
        self.assertIn(response.status_code, [401, 403])

    def test_friends_list_requires_auth(self):
        response = self.client.get("/api/friends/")
        self.assertIn(response.status_code, [401, 403])

    def test_friend_requests_list_requires_auth(self):
        response = self.client.get("/api/friend-requests/")
        self.assertIn(response.status_code, [401, 403])

    def test_send_friend_request_requires_auth(self):
        response = self.client.post(
            "/api/friends/send-request/",
            data=json.dumps({"code": "ABC"}),
            content_type="application/json",
        )
        self.assertIn(response.status_code, [401, 403])

    def test_edit_recipes_requests_requires_auth(self):
        response = self.client.get("/api/edit-recipes-requests/")
        self.assertIn(response.status_code, [401, 403])


class IngredientApiEdgeCaseTests(TestCase):
    """Edge cases for ingredient API."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)

    def test_create_ingredient_with_float_values(self):
        response = self.client.post(
            "/api/ingredients/",
            data=json.dumps(
                {
                    "name": "Olive Oil",
                    "calories": 884.5,
                    "protein": 0.0,
                    "fat": 100.0,
                    "carbs": 0.0,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertAlmostEqual(response.json()["calories"], 884.5)

    def test_delete_other_users_ingredient_forbidden(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        ing = Ingredient.objects.create(user=other, name="Secret", calories=0)
        response = self.client.delete(f"/api/ingredients/{ing.id}/")
        self.assertEqual(response.status_code, 403)

    def test_list_ingredients_returns_all_users(self):
        """Ingredients from all users should be visible in the list."""
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        Ingredient.objects.create(user=self.user, name="Mine")
        Ingredient.objects.create(user=other, name="Other")
        response = self.client.get("/api/ingredients/")
        self.assertEqual(response.status_code, 200)
        names = {i["name"] for i in response.json()}
        self.assertIn("Mine", names)
        self.assertIn("Other", names)

    def test_retrieve_ingredient_not_allowed(self):
        ing = Ingredient.objects.create(user=self.user, name="X")
        response = self.client.get(f"/api/ingredients/{ing.id}/")
        self.assertEqual(response.status_code, 405)

    def test_update_ingredient_success(self):
        ing = Ingredient.objects.create(
            user=self.user,
            name="Old Name",
            calories=100,
            protein=10,
            fat=5,
            carbs=20,
        )
        response = self.client.patch(
            f"/api/ingredients/{ing.id}/",
            data=json.dumps(
                {
                    "name": "New Name",
                    "calories": 150,
                    "protein": 15,
                    "fat": 8,
                    "carbs": 25,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "New Name")
        self.assertEqual(data["calories"], 150)
        ing.refresh_from_db()
        self.assertEqual(ing.name, "New Name")
        self.assertEqual(ing.calories, 150)

    def test_update_other_users_ingredient_forbidden(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        ing = Ingredient.objects.create(user=other, name="Secret", calories=0)
        response = self.client.patch(
            f"/api/ingredients/{ing.id}/",
            data=json.dumps({"name": "Hacked"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


class RecipeApiEdgeCaseTests(TestCase):
    """Edge cases for recipe API."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)
        self.ing = Ingredient.objects.create(user=self.user, name="Tomato", calories=18)

    def test_recipe_list_includes_other_users_recipes(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        Recipe.objects.create(
            user=self.user, name="My Recipe", description="", instructions=""
        )
        Recipe.objects.create(
            user=other, name="Bob Recipe", description="", instructions=""
        )
        response = self.client.get("/api/recipes/")
        names = {r["name"] for r in response.json()}
        self.assertIn("My Recipe", names)
        self.assertIn("Bob Recipe", names)

    def test_recipe_delete_other_users_recipe_forbidden(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        recipe = Recipe.objects.create(
            user=other, name="Private", description="", instructions=""
        )
        response = self.client.delete(f"/api/recipes/{recipe.id}/")
        self.assertEqual(response.status_code, 403)

    def test_recipe_update_other_users_recipe_forbidden(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        recipe = Recipe.objects.create(
            user=other, name="Private", description="", instructions=""
        )
        response = self.client.put(
            f"/api/recipes/{recipe.id}/",
            data=json.dumps(
                {
                    "name": "Hacked",
                    "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 50}],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_recipe_create_sets_current_user_as_owner(self):
        response = self.client.post(
            "/api/recipes/",
            data=json.dumps(
                {
                    "name": "My Salad",
                    "description": "",
                    "instructions": "",
                    "ingredients": [
                        {"ingredient_id": self.ing.id, "weight_grams": 100}
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        recipe = Recipe.objects.get(name="My Salad")
        self.assertEqual(recipe.user, self.user)

    def test_recipe_create_calculates_nutrition(self):
        response = self.client.post(
            "/api/recipes/",
            data=json.dumps(
                {
                    "name": "Tomato Soup",
                    "description": "",
                    "instructions": "",
                    "ingredients": [
                        {"ingredient_id": self.ing.id, "weight_grams": 200}
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertAlmostEqual(data["total_calories"], 36.0)


class MenuApiEdgeCaseTests(TestCase):
    """Edge cases for menu API endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)

    def test_legacy_menu_creates_default_menu(self):
        response = self.client.get("/api/menu/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Menu.objects.filter(user=self.user).exists())

    def test_legacy_menu_put_invalid_body(self):
        response = self.client.put(
            "/api/menu/",
            data=json.dumps("not a dict"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_menu_detail_put_invalid_body(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        response = self.client.put(
            f"/api/menus/{menu.id}/",
            data=json.dumps("not a dict"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_menu_put_with_invalid_slot_keys_ignored(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        body = {
            "invalid": recipe.id,
            "99-99": recipe.id,
            "0-0": recipe.id,
        }
        response = self.client.put(
            f"/api/menus/{menu.id}/",
            data=json.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MenuSlot.objects.filter(menu=menu).count(), 1)

    def test_menu_put_with_invalid_recipe_id_ignored(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        body = {"0-0": 99999}
        response = self.client.put(
            f"/api/menus/{menu.id}/",
            data=json.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MenuSlot.objects.filter(menu=menu).count(), 0)

    def test_menu_put_with_null_value_skipped(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        body = {"0-0": None}
        response = self.client.put(
            f"/api/menus/{menu.id}/",
            data=json.dumps(body),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MenuSlot.objects.filter(menu=menu).count(), 0)

    def test_menu_put_replaces_all_existing_slots(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        MenuSlot.objects.create(menu=menu, day_of_week=0, meal_type=0, recipe=recipe)
        MenuSlot.objects.create(menu=menu, day_of_week=1, meal_type=1, recipe=recipe)
        body = {"2-2": recipe.id}
        self.client.put(
            f"/api/menus/{menu.id}/",
            data=json.dumps(body),
            content_type="application/json",
        )
        slots = list(MenuSlot.objects.filter(menu=menu))
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].day_of_week, 2)
        self.assertEqual(slots[0].meal_type, 2)


class MenuSetPrimaryTests(TestCase):
    """Test set-primary endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)

    def test_set_primary(self):
        menu1 = Menu.objects.create(user=self.user, name="A", is_primary=True)
        menu2 = Menu.objects.create(user=self.user, name="B")
        response = self.client.post(f"/api/menus/{menu2.id}/set-primary/")
        self.assertEqual(response.status_code, 200)
        menu1.refresh_from_db()
        menu2.refresh_from_db()
        self.assertFalse(menu1.is_primary)
        self.assertTrue(menu2.is_primary)

    def test_set_primary_other_users_menu_404(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        menu = Menu.objects.create(user=other, name="Other")
        response = self.client.post(f"/api/menus/{menu.id}/set-primary/")
        self.assertEqual(response.status_code, 404)


class ShoppingListEdgeCaseTests(TestCase):
    """Edge cases for shopping list API."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)

    def test_shopping_list_with_menu_id(self):
        menu = Menu.objects.create(user=self.user, name="Test")
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        ing = Ingredient.objects.create(user=self.user, name="X", calories=50)
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ing, weight_grams=100)
        today = date.today()
        MenuSlot.objects.create(
            menu=menu, day_of_week=today.weekday(), meal_type=0, recipe=recipe
        )
        response = self.client.post(
            "/api/shopping-list/",
            data=json.dumps(
                {
                    "start_date": today.isoformat(),
                    "end_date": today.isoformat(),
                    "people_count": 1,
                    "menu_id": menu.id,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "X")

    def test_shopping_list_with_invalid_menu_id_404(self):
        response = self.client.post(
            "/api/shopping-list/",
            data=json.dumps(
                {
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-07",
                    "menu_id": 99999,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_shopping_list_other_users_menu_id_404(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        menu = Menu.objects.create(user=other, name="Other")
        response = self.client.post(
            "/api/shopping-list/",
            data=json.dumps(
                {
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-07",
                    "menu_id": menu.id,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


class FriendsApiEdgeCaseTests(TestCase):
    """Edge cases for friends API."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)

    def test_send_request_missing_code(self):
        response = self.client.post(
            "/api/friends/send-request/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_send_request_already_pending(self):
        """Sending a second request when a pending one exists should still create."""
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        code_obj = UserFriendCode.objects.create(user=other)
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_PENDING,
        )
        response = self.client.post(
            "/api/friends/send-request/",
            data=json.dumps({"code": code_obj.code}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)

    def test_accept_request_wrong_user(self):
        """Only to_user can accept a friend request."""
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        fr = FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_PENDING,
        )
        response = self.client.post(f"/api/friend-requests/{fr.id}/accept/")
        self.assertEqual(response.status_code, 404)

    def test_decline_request_wrong_user(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        fr = FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_PENDING,
        )
        response = self.client.post(f"/api/friend-requests/{fr.id}/decline/")
        self.assertEqual(response.status_code, 404)

    def test_accept_already_accepted_request(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        fr = FriendRequest.objects.create(
            from_user=other,
            to_user=self.user,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        response = self.client.post(f"/api/friend-requests/{fr.id}/accept/")
        self.assertEqual(response.status_code, 400)

    def test_remove_nonexistent_friend(self):
        response = self.client.post("/api/friends/99999/remove/")
        self.assertEqual(response.status_code, 400)

    def test_friend_menu_returns_empty_when_no_menu(self):
        other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        response = self.client.get(f"/api/friends/{other.id}/menu/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["menu"], {})
        self.assertEqual(data["recipes"], [])


class FriendShoppingListEdgeCaseTests(TestCase):
    """Edge cases for friend shopping list."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)
        self.friend = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.friend,
            status=FriendRequest.STATUS_ACCEPTED,
        )

    def test_friend_shopping_list_returns_empty_when_no_menu(self):
        today = date.today()
        response = self.client.post(
            f"/api/friends/{self.friend.id}/shopping-list/",
            data=json.dumps(
                {
                    "start_date": today.isoformat(),
                    "end_date": (today + timedelta(days=6)).isoformat(),
                    "people_count": 2,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_friend_shopping_list_with_specific_menu_id(self):
        menu = Menu.objects.create(user=self.friend, name="Friend Menu")
        recipe = Recipe.objects.create(
            user=self.friend, name="R", description="", instructions=""
        )
        ing = Ingredient.objects.create(user=self.friend, name="X", calories=50)
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ing, weight_grams=100)
        today = date.today()
        MenuSlot.objects.create(
            menu=menu, day_of_week=today.weekday(), meal_type=0, recipe=recipe
        )
        response = self.client.post(
            f"/api/friends/{self.friend.id}/shopping-list/",
            data=json.dumps(
                {
                    "start_date": today.isoformat(),
                    "end_date": today.isoformat(),
                    "people_count": 1,
                    "menu_id": menu.id,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "X")


class EditRecipesRequestEdgeCaseTests(TestCase):
    """Edge cases for edit-recipes request flow."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)
        self.other = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )

    def test_send_edit_request_not_friends_400(self):
        response = self.client.post(
            f"/api/friends/{self.other.id}/send-edit-recipes-request/"
        )
        self.assertEqual(response.status_code, 400)

    def test_revoke_when_not_active_400(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_NONE,
        )
        response = self.client.post(
            f"/api/friends/{self.other.id}/revoke-edit-recipes/"
        )
        self.assertEqual(response.status_code, 400)

    def test_revoke_not_friends_400(self):
        response = self.client.post(
            f"/api/friends/{self.other.id}/revoke-edit-recipes/"
        )
        self.assertEqual(response.status_code, 400)

    def test_accept_nonexistent_request_404(self):
        response = self.client.post("/api/edit-recipes-requests/99999/accept/")
        self.assertEqual(response.status_code, 404)

    def test_decline_nonexistent_request_404(self):
        response = self.client.post("/api/edit-recipes-requests/99999/decline/")
        self.assertEqual(response.status_code, 404)

    def test_already_accepted_edit_request_cannot_be_accepted_again(self):
        fr = FriendRequest.objects.create(
            from_user=self.other,
            to_user=self.user,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
            can_edit_recipes_requested_by=self.other,
        )
        response = self.client.post(f"/api/edit-recipes-requests/{fr.id}/accept/")
        self.assertEqual(response.status_code, 400)


class FriendMenuEdgeCaseTests(TestCase):
    """Edge cases for friend menu CRUD endpoints."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)
        self.friend = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )

    def _make_friends_with_edit(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.friend,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )

    def test_friend_menu_detail_nonexistent_menu_404(self):
        self._make_friends_with_edit()
        response = self.client.get(f"/api/friends/{self.friend.id}/menus/99999/")
        self.assertEqual(response.status_code, 404)

    def test_friend_menu_put_invalid_body_400(self):
        self._make_friends_with_edit()
        menu = Menu.objects.create(user=self.friend, name="Test")
        response = self.client.put(
            f"/api/friends/{self.friend.id}/menus/{menu.id}/",
            data=json.dumps("not a dict"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_friend_menu_patch_without_name_keeps_original(self):
        self._make_friends_with_edit()
        menu = Menu.objects.create(user=self.friend, name="Original")
        response = self.client.patch(
            f"/api/friends/{self.friend.id}/menus/{menu.id}/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        menu.refresh_from_db()
        self.assertEqual(menu.name, "Original")

    def test_not_friends_cannot_access_friend_menus(self):
        stranger = User.objects.create_user(
            username="stranger", password="pass", email="stranger@test.com"
        )
        response = self.client.get(f"/api/friends/{stranger.id}/menus/")
        self.assertEqual(response.status_code, 400)

    def test_friend_menus_create_default_name(self):
        self._make_friends_with_edit()
        response = self.client.post(
            f"/api/friends/{self.friend.id}/menus/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Меню на неделю")
