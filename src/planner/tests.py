"""API tests for ingredients, recipes, menu, and shopping-list (contract tests)."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from planner.models import Ingredient, MenuSlot, Recipe, RecipeIngredient

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
