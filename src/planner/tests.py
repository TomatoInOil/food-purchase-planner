"""API tests for ingredients, recipes, menu, and shopping-list (contract tests)."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from planner.models import (
    FriendRequest,
    Ingredient,
    MenuSlot,
    Recipe,
    RecipeIngredient,
    UserFriendCode,
)

User = get_user_model()


class ApiTestBase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", email="test@example.com"
        )
        self.client.force_login(self.user)


class IngredientApiTests(ApiTestBase):
    def test_ingredient_list_empty(self):
        response = self.client.get("/api/ingredients/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_ingredient_list_returns_contract(self):
        ing = Ingredient.objects.create(
            user=self.user,
            name="Flour",
            calories=364,
            protein=10,
            fat=1,
            carbs=76,
        )
        response = self.client.get("/api/ingredients/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], ing.id)
        self.assertEqual(data[0]["name"], "Flour")
        self.assertEqual(data[0]["calories"], 364)
        self.assertEqual(data[0]["protein"], 10)
        self.assertEqual(data[0]["fat"], 1)
        self.assertEqual(data[0]["carbs"], 76)
        self.assertIs(data[0]["is_owner"], True)

    def test_ingredient_create_success(self):
        response = self.client.post(
            "/api/ingredients/",
            data='{"name":"Salt","calories":0,"protein":0,"fat":0,"carbs":0}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("id", data)
        self.assertEqual(data["name"], "Salt")
        self.assertIs(data["is_owner"], True)

    def test_ingredient_create_duplicate_name_400(self):
        Ingredient.objects.create(user=self.user, name="Salt", calories=0)
        response = self.client.post(
            "/api/ingredients/",
            data='{"name":"Salt","calories":0,"protein":0,"fat":0,"carbs":0}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_ingredient_delete_success(self):
        ing = Ingredient.objects.create(user=self.user, name="X", calories=0)
        response = self.client.delete(f"/api/ingredients/{ing.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertFalse(Ingredient.objects.filter(pk=ing.id).exists())

    def test_ingredient_delete_not_found_404(self):
        response = self.client.delete("/api/ingredients/99999/")
        self.assertEqual(response.status_code, 404)

    def test_ingredient_delete_used_in_recipe_400(self):
        ing = Ingredient.objects.create(user=self.user, name="X", calories=0)
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ing, weight_grams=100)
        response = self.client.delete(f"/api/ingredients/{ing.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_ingredient_delete_system_ingredient_400(self):
        system_user = User.objects.create_user(
            username="system", password="x", email="system@local"
        )
        ing = Ingredient.objects.create(user=system_user, name="SystemIng", calories=0)
        self.client.force_login(system_user)
        response = self.client.delete(f"/api/ingredients/{ing.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


class RecipeApiTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.ing1 = Ingredient.objects.create(
            user=self.user, name="A", calories=100, protein=10, fat=1, carbs=5
        )
        self.ing2 = Ingredient.objects.create(
            user=self.user, name="B", calories=200, protein=20, fat=2, carbs=10
        )

    def test_recipe_list_empty(self):
        response = self.client.get("/api/recipes/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_recipe_list_returns_contract(self):
        recipe = Recipe.objects.create(
            user=self.user, name="Soup", description="d", instructions="i"
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing1, weight_grams=150
        )
        response = self.client.get("/api/recipes/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        r = data[0]
        self.assertEqual(r["id"], recipe.id)
        self.assertEqual(r["name"], "Soup")
        self.assertIn("ingredients", r)
        self.assertEqual(len(r["ingredients"]), 1)
        self.assertEqual(r["ingredients"][0]["ingredient_id"], self.ing1.id)
        self.assertEqual(r["ingredients"][0]["ingredient_name"], "A")
        self.assertEqual(r["ingredients"][0]["weight_grams"], 150)
        self.assertIn("author_username", r)
        self.assertIs(r["is_owner"], True)

    def test_recipe_create_success(self):
        body = {
            "name": "Salad",
            "description": "Green",
            "instructions": "Mix",
            "ingredients": [
                {"ingredient_id": self.ing1.id, "weight_grams": 100},
                {"ingredient_id": self.ing2.id, "weight_grams": 50},
            ],
        }
        response = self.client.post(
            "/api/recipes/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Salad")
        self.assertEqual(len(data["ingredients"]), 2)
        self.assertEqual(data["total_calories"], 100 * 1.0 + 200 * 0.5)

    def test_recipe_create_no_name_400(self):
        response = self.client.post(
            "/api/recipes/",
            data={
                "name": "",
                "ingredients": [{"ingredient_id": self.ing1.id, "weight_grams": 100}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_recipe_create_no_ingredients_400(self):
        response = self.client.post(
            "/api/recipes/",
            data={"name": "X", "ingredients": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_recipe_retrieve(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing1, weight_grams=200
        )
        response = self.client.get(f"/api/recipes/{recipe.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "R")
        self.assertEqual(data["ingredients"][0]["weight_grams"], 200)

    def test_recipe_retrieve_404(self):
        response = self.client.get("/api/recipes/99999/")
        self.assertEqual(response.status_code, 404)

    def test_recipe_update_success(self):
        recipe = Recipe.objects.create(
            user=self.user, name="Old", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=recipe, ingredient=self.ing1, weight_grams=100
        )
        body = {
            "name": "New",
            "description": "d2",
            "instructions": "i2",
            "ingredients": [{"ingredient_id": self.ing2.id, "weight_grams": 50}],
        }
        response = self.client.put(
            f"/api/recipes/{recipe.id}/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "New")
        self.assertEqual(len(data["ingredients"]), 1)
        self.assertEqual(data["ingredients"][0]["ingredient_id"], self.ing2.id)

    def test_recipe_delete_success(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        response = self.client.delete(f"/api/recipes/{recipe.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertFalse(Recipe.objects.filter(pk=recipe.id).exists())


class RecipeFriendEditorTests(ApiTestBase):
    """Verify that mutual edit-recipes sharing works correctly."""

    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(
            username="owner", password="pass", email="owner@example.com"
        )
        self.ing = Ingredient.objects.create(
            user=self.owner, name="Tomato", calories=18, protein=1, fat=0, carbs=4
        )
        self.recipe = Recipe.objects.create(
            user=self.owner, name="Soup", description="d", instructions="i"
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing, weight_grams=100
        )

    def _grant_friend_edit(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.owner,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
            can_edit_recipes_requested_by=self.user,
        )

    def test_friend_editor_can_update_recipe(self):
        self._grant_friend_edit()
        body = {
            "name": "Updated Soup",
            "description": "new d",
            "instructions": "new i",
            "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 200}],
        }
        response = self.client.put(
            f"/api/recipes/{self.recipe.id}/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Updated Soup")

    def test_friend_editor_can_delete_recipe(self):
        self._grant_friend_edit()
        response = self.client.delete(f"/api/recipes/{self.recipe.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertFalse(Recipe.objects.filter(pk=self.recipe.id).exists())

    def test_non_friend_cannot_update_recipe(self):
        body = {
            "name": "Hacked",
            "description": "x",
            "instructions": "x",
            "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 50}],
        }
        response = self.client.put(
            f"/api/recipes/{self.recipe.id}/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_non_friend_cannot_delete_recipe(self):
        response = self.client.delete(f"/api/recipes/{self.recipe.id}/")
        self.assertEqual(response.status_code, 403)

    def test_friend_without_edit_permission_cannot_update(self):
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.owner,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_NONE,
        )
        body = {
            "name": "Hacked",
            "description": "x",
            "instructions": "x",
            "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 50}],
        }
        response = self.client.put(
            f"/api/recipes/{self.recipe.id}/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_pending_edit_recipes_does_not_grant_permission(self):
        """A pending sharing request must NOT grant edit access."""
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.owner,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_PENDING,
            can_edit_recipes_requested_by=self.user,
        )
        body = {
            "name": "Hacked",
            "description": "x",
            "instructions": "x",
            "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 50}],
        }
        response = self.client.put(
            f"/api/recipes/{self.recipe.id}/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_accepted_edit_recipes_is_bidirectional(self):
        """Once accepted, both friends can edit each other's recipes."""
        self._grant_friend_edit()
        my_recipe = Recipe.objects.create(
            user=self.user, name="My Soup", description="d", instructions="i"
        )
        RecipeIngredient.objects.create(
            recipe=my_recipe, ingredient=self.ing, weight_grams=100
        )

        owner_client = Client()
        owner_client.force_login(self.owner)
        body = {
            "name": "Updated My Soup",
            "description": "new d",
            "instructions": "new i",
            "ingredients": [{"ingredient_id": self.ing.id, "weight_grams": 200}],
        }
        response = owner_client.put(
            f"/api/recipes/{my_recipe.id}/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Updated My Soup")


class MenuApiTests(ApiTestBase):
    def test_menu_get_empty_returns_all_slots(self):
        response = self.client.get("/api/menu/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for day in range(7):
            for meal in range(4):
                self.assertIn(f"{day}-{meal}", data)
                self.assertIsNone(data[f"{day}-{meal}"])

    def test_menu_put_and_get(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        body = {"0-0": recipe.id, "1-1": recipe.id}
        response = self.client.put(
            "/api/menu/",
            data=body,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        response2 = self.client.get("/api/menu/")
        self.assertEqual(response2.status_code, 200)
        data = response2.json()
        self.assertEqual(data["0-0"], recipe.id)
        self.assertEqual(data["1-1"], recipe.id)
        self.assertIsNone(data["0-1"])


class ShoppingListApiTests(ApiTestBase):
    def test_shopping_list_requires_dates(self):
        response = self.client.post(
            "/api/shopping-list/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_shopping_list_returns_list_format(self):
        recipe = Recipe.objects.create(
            user=self.user, name="R", description="", instructions=""
        )
        ing = Ingredient.objects.create(
            user=self.user, name="Tomato", calories=18, protein=1, fat=0, carbs=4
        )
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ing, weight_grams=100)
        start = date.today()
        end = start + timedelta(days=1)
        MenuSlot.objects.create(
            user=self.user,
            day_of_week=start.weekday(),
            meal_type=0,
            recipe=recipe,
        )
        response = self.client.post(
            "/api/shopping-list/",
            data={
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "people_count": 2,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Tomato")
        self.assertEqual(data[0]["weight_grams"], 200)


class FriendsApiTests(ApiTestBase):
    def test_my_code_creates_and_returns_same_code(self):
        response1 = self.client.get("/api/friends/my-code/")
        self.assertEqual(response1.status_code, 200)
        data1 = response1.json()
        self.assertIn("code", data1)
        code1 = data1["code"]
        self.assertTrue(
            UserFriendCode.objects.filter(user=self.user, code=code1).exists()
        )

        response2 = self.client.get("/api/friends/my-code/")
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2["code"], code1)

    def test_send_request_creates_pending_request_by_code(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        code_obj = UserFriendCode.objects.create(user=other)

        response = self.client.post(
            "/api/friends/send-request/",
            data={"code": code_obj.code},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], FriendRequest.STATUS_PENDING)
        self.assertEqual(data["from_user_id"], self.user.id)
        self.assertEqual(data["to_user_id"], other.id)

    def test_send_request_self_request_400(self):
        code_obj = UserFriendCode.objects.create(user=self.user)
        response = self.client.post(
            "/api/friends/send-request/",
            data={"code": code_obj.code},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_send_request_user_not_found_400(self):
        response = self.client.post(
            "/api/friends/send-request/",
            data={"code": "UNKNOWN"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_send_request_already_friends_400(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        code_obj = UserFriendCode.objects.create(user=other)
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_ACCEPTED,
        )

        response = self.client.post(
            "/api/friends/send-request/",
            data={"code": code_obj.code},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_friend_requests_list_shows_incoming_pending_only(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        FriendRequest.objects.create(
            from_user=other,
            to_user=self.user,
            status=FriendRequest.STATUS_PENDING,
        )
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_PENDING,
        )
        FriendRequest.objects.create(
            from_user=other,
            to_user=self.user,
            status=FriendRequest.STATUS_ACCEPTED,
        )

        response = self.client.get("/api/friend-requests/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["from_user_id"], other.id)
        self.assertEqual(data[0]["status"], FriendRequest.STATUS_PENDING)

    def test_accept_request_marks_accepted_and_cancels_reverse_pending(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        incoming = FriendRequest.objects.create(
            from_user=other,
            to_user=self.user,
            status=FriendRequest.STATUS_PENDING,
        )
        reverse = FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_PENDING,
        )

        response = self.client.post(f"/api/friend-requests/{incoming.id}/accept/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], FriendRequest.STATUS_ACCEPTED)

        incoming.refresh_from_db()
        reverse.refresh_from_db()
        self.assertEqual(incoming.status, FriendRequest.STATUS_ACCEPTED)
        self.assertEqual(reverse.status, FriendRequest.STATUS_CANCELLED)

    def test_decline_request_marks_declined(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        incoming = FriendRequest.objects.create(
            from_user=other,
            to_user=self.user,
            status=FriendRequest.STATUS_PENDING,
        )

        response = self.client.post(f"/api/friend-requests/{incoming.id}/decline/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], FriendRequest.STATUS_DECLINED)

        incoming.refresh_from_db()
        self.assertEqual(incoming.status, FriendRequest.STATUS_DECLINED)

    def test_friends_list_returns_accepted_friends(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        accepted = FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        FriendRequest.objects.create(
            from_user=other,
            to_user=self.user,
            status=FriendRequest.STATUS_PENDING,
        )

        response = self.client.get("/api/friends/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        friend = data[0]
        self.assertEqual(friend["user_id"], other.id)
        self.assertEqual(friend["username"], other.username)
        self.assertEqual(friend["friend_request_id"], accepted.id)

    def test_remove_friend_changes_status_to_removed_and_errors_if_not_friend(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        accepted = FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_ACCEPTED,
        )

        response_ok = self.client.post(f"/api/friends/{other.id}/remove/")
        self.assertEqual(response_ok.status_code, 200)
        self.assertEqual(response_ok.json(), {"success": True})
        accepted.refresh_from_db()
        self.assertEqual(accepted.status, FriendRequest.STATUS_REMOVED)

        response_err = self.client.post(f"/api/friends/{other.id}/remove/")
        self.assertEqual(response_err.status_code, 400)
        self.assertIn("error", response_err.json())

    def test_friend_menu_returns_menu_and_recipes_when_friends(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        recipe = Recipe.objects.create(
            user=other, name="Friend Soup", description="", instructions=""
        )
        MenuSlot.objects.create(user=other, day_of_week=0, meal_type=0, recipe=recipe)

        response = self.client.get(f"/api/friends/{other.id}/menu/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("menu", data)
        self.assertIn("recipes", data)
        self.assertEqual(data["menu"]["0-0"], recipe.id)
        self.assertEqual(len(data["recipes"]), 1)
        self.assertEqual(data["recipes"][0]["id"], recipe.id)
        self.assertEqual(data["recipes"][0]["name"], "Friend Soup")

    def test_friend_menu_400_when_not_friends(self):
        other = User.objects.create_user(
            username="stranger", password="pass", email="stranger@example.com"
        )

        response = self.client.get(f"/api/friends/{other.id}/menu/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_friend_shopping_list_returns_same_format_as_own_when_friends(self):
        other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        FriendRequest.objects.create(
            from_user=self.user,
            to_user=other,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        recipe = Recipe.objects.create(
            user=other, name="R", description="", instructions=""
        )
        ing = Ingredient.objects.create(
            user=other, name="FriendTomato", calories=18, protein=1, fat=0, carbs=4
        )
        RecipeIngredient.objects.create(recipe=recipe, ingredient=ing, weight_grams=100)
        start = date.today()
        end = start + timedelta(days=1)
        MenuSlot.objects.create(
            user=other, day_of_week=start.weekday(), meal_type=0, recipe=recipe
        )

        response = self.client.post(
            f"/api/friends/{other.id}/shopping-list/",
            data={
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "people_count": 2,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "FriendTomato")
        self.assertEqual(data[0]["weight_grams"], 200)

    def test_friend_shopping_list_400_when_not_friends(self):
        other = User.objects.create_user(
            username="stranger", password="pass", email="stranger@example.com"
        )
        start = date.today()
        end = start + timedelta(days=1)

        response = self.client.post(
            f"/api/friends/{other.id}/shopping-list/",
            data={
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())


class EditRecipesRequestFlowTests(ApiTestBase):
    """Test the full send → accept/decline → revoke flow for edit-recipes requests."""

    def setUp(self):
        super().setUp()
        self.other = User.objects.create_user(
            username="friend", password="pass", email="friend@example.com"
        )
        self.fr = FriendRequest.objects.create(
            from_user=self.user,
            to_user=self.other,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        self.other_client = Client()
        self.other_client.force_login(self.other)

    def test_send_edit_recipes_request(self):
        response = self.client.post(
            f"/api/friends/{self.other.id}/send-edit-recipes-request/"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["can_edit_recipes_status"], "pending")

        self.fr.refresh_from_db()
        self.assertEqual(
            self.fr.can_edit_recipes_status, FriendRequest.EDIT_RECIPES_PENDING
        )
        self.assertEqual(self.fr.can_edit_recipes_requested_by_id, self.user.id)

    def test_send_duplicate_request_400(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_PENDING
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.client.post(
            f"/api/friends/{self.other.id}/send-edit-recipes-request/"
        )
        self.assertEqual(response.status_code, 400)

    def test_incoming_edit_recipes_requests_list(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_PENDING
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.other_client.get("/api/edit-recipes-requests/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["friend_request_id"], self.fr.id)
        self.assertEqual(data[0]["requested_by_id"], self.user.id)

    def test_sender_does_not_see_own_request(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_PENDING
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.client.get("/api/edit-recipes-requests/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

    def test_accept_edit_recipes_request(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_PENDING
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.other_client.post(
            f"/api/edit-recipes-requests/{self.fr.id}/accept/"
        )
        self.assertEqual(response.status_code, 200)

        self.fr.refresh_from_db()
        self.assertEqual(
            self.fr.can_edit_recipes_status, FriendRequest.EDIT_RECIPES_ACCEPTED
        )

    def test_decline_edit_recipes_request(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_PENDING
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.other_client.post(
            f"/api/edit-recipes-requests/{self.fr.id}/decline/"
        )
        self.assertEqual(response.status_code, 200)

        self.fr.refresh_from_db()
        self.assertEqual(
            self.fr.can_edit_recipes_status, FriendRequest.EDIT_RECIPES_NONE
        )
        self.assertIsNone(self.fr.can_edit_recipes_requested_by)

    def test_sender_cannot_accept_own_request(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_PENDING
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.client.post(
            f"/api/edit-recipes-requests/{self.fr.id}/accept/"
        )
        self.assertEqual(response.status_code, 404)

    def test_revoke_edit_recipes(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_ACCEPTED
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.client.post(
            f"/api/friends/{self.other.id}/revoke-edit-recipes/"
        )
        self.assertEqual(response.status_code, 200)

        self.fr.refresh_from_db()
        self.assertEqual(
            self.fr.can_edit_recipes_status, FriendRequest.EDIT_RECIPES_NONE
        )

    def test_other_user_can_revoke_too(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_ACCEPTED
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.other_client.post(
            f"/api/friends/{self.user.id}/revoke-edit-recipes/"
        )
        self.assertEqual(response.status_code, 200)

        self.fr.refresh_from_db()
        self.assertEqual(
            self.fr.can_edit_recipes_status, FriendRequest.EDIT_RECIPES_NONE
        )

    def test_friends_list_shows_edit_recipes_status(self):
        self.fr.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_ACCEPTED
        self.fr.can_edit_recipes_requested_by = self.user
        self.fr.save()

        response = self.client.get("/api/friends/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["can_edit_recipes"])
        self.assertEqual(data[0]["can_edit_recipes_status"], "accepted")
