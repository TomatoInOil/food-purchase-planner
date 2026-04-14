"""Tests for MCP server tools, helpers, auth middleware, and OAuth2 endpoints."""

import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from starlette.testclient import TestClient

from planner.mcp_server import (
    DAY_NAMES_RU,
    MEAL_TYPE_NAMES_RU,
    _build_app,
    _build_day_data,
    _build_recipe_data,
    _get_user,
    _sync_get_shopping_list,
    _sync_get_todays_menu,
    _sync_get_week_menu,
)
from planner.models import (
    Ingredient,
    Menu,
    MenuSlot,
    Recipe,
    RecipeIngredient,
    UserActiveMenu,
)

User = get_user_model()


class GetUserTests(TestCase):
    """Test _get_user helper."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@test.com")

    def test_valid_username_returns_user(self):
        result = _get_user("alice")
        assert result == self.user

    def test_invalid_username_returns_none(self):
        result = _get_user("nonexistent")
        assert result is None


class BuildRecipeDataTests(TestCase):
    """Test _build_recipe_data helper."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@test.com")
        self.recipe = Recipe.objects.create(
            user=self.user,
            name="Salad",
            description="Fresh salad",
            instructions="Mix everything",
        )
        self.tomato = Ingredient.objects.create(
            user=self.user, name="Tomato", calories=18, protein=0.9, fat=0.2, carbs=3.9
        )
        self.cheese = Ingredient.objects.create(
            user=self.user, name="Cheese", calories=300, protein=25, fat=20, carbs=2
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.tomato, weight_grams=200
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.cheese, weight_grams=50
        )
        self.recipe.refresh_from_db()

    def test_returns_correct_structure(self):
        data = _build_recipe_data(self.recipe)
        assert data["name"] == "Salad"
        assert data["description"] == "Fresh salad"
        assert data["instructions"] == "Mix everything"
        assert isinstance(data["ingredients"], list)
        assert len(data["ingredients"]) == 2
        assert isinstance(data["nutrition"], dict)

    def test_uses_total_nutrition_fields(self):
        data = _build_recipe_data(self.recipe)
        assert data["nutrition"]["calories"] == self.recipe.total_calories
        assert data["nutrition"]["protein"] == self.recipe.total_protein
        assert data["nutrition"]["fat"] == self.recipe.total_fat
        assert data["nutrition"]["carbs"] == self.recipe.total_carbs

    def test_ingredients_from_recipe_ingredients(self):
        data = _build_recipe_data(self.recipe)
        names = {i["name"] for i in data["ingredients"]}
        assert names == {"Tomato", "Cheese"}
        tomato = next(i for i in data["ingredients"] if i["name"] == "Tomato")
        assert tomato["weight_grams"] == 200

    def test_empty_description_and_instructions(self):
        recipe = Recipe.objects.create(
            user=self.user, name="Empty", description="", instructions=""
        )
        data = _build_recipe_data(recipe)
        assert data["description"] == ""
        assert data["instructions"] == ""


class BuildDayDataTests(TestCase):
    """Test _build_day_data helper."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@test.com")
        self.menu = Menu.objects.create(user=self.user, name="Test Menu")
        self.recipe_a = Recipe.objects.create(
            user=self.user, name="Omelette", description="", instructions=""
        )
        self.recipe_b = Recipe.objects.create(
            user=self.user, name="Soup", description="", instructions=""
        )

    def test_returns_date_and_day_of_week(self):
        data = _build_day_data(self.menu, 0)
        assert data["day_of_week"] == DAY_NAMES_RU[0]
        assert "date" in data
        parsed = date.fromisoformat(data["date"])
        assert parsed.weekday() == 0

    def test_empty_day_returns_empty_meals(self):
        data = _build_day_data(self.menu, 3)
        assert data["meals"] == []

    def test_single_meal_single_recipe(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=2, meal_type=0, recipe=self.recipe_a
        )
        data = _build_day_data(self.menu, 2)
        assert len(data["meals"]) == 1
        assert data["meals"][0]["meal_type"] == MEAL_TYPE_NAMES_RU[0]
        assert len(data["meals"][0]["recipes"]) == 1
        assert data["meals"][0]["recipes"][0]["name"] == "Omelette"

    def test_multiple_meals_ordered_by_meal_type(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=1, meal_type=3, recipe=self.recipe_b
        )
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=1, meal_type=0, recipe=self.recipe_a
        )
        data = _build_day_data(self.menu, 1)
        assert len(data["meals"]) == 2
        assert data["meals"][0]["meal_type"] == MEAL_TYPE_NAMES_RU[0]
        assert data["meals"][1]["meal_type"] == MEAL_TYPE_NAMES_RU[3]

    def test_multiple_recipes_in_same_meal(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=4, meal_type=1, recipe=self.recipe_a
        )
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=4, meal_type=1, recipe=self.recipe_b
        )
        data = _build_day_data(self.menu, 4)
        assert len(data["meals"]) == 1
        assert len(data["meals"][0]["recipes"]) == 2

    def test_servings_included_in_recipe_data(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe_a, servings=3
        )
        data = _build_day_data(self.menu, 0)
        assert data["meals"][0]["recipes"][0]["servings"] == 3

    def test_slot_with_null_recipe_excluded(self):
        MenuSlot.objects.create(menu=self.menu, day_of_week=5, meal_type=0, recipe=None)
        data = _build_day_data(self.menu, 5)
        assert data["meals"] == []


class SyncGetTodaysMenuTests(TestCase):
    """Test _sync_get_todays_menu."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@test.com")
        self.menu = Menu.objects.create(user=self.user, name="Weekly")
        UserActiveMenu.objects.create(user=self.user, menu=self.menu)

    def test_user_not_found_returns_error(self):
        result = json.loads(_sync_get_todays_menu("nonexistent"))
        assert "error" in result
        assert "nonexistent" in result["error"]

    def test_valid_user_returns_today_structure(self):
        recipe = Recipe.objects.create(
            user=self.user, name="Toast", description="", instructions=""
        )
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=recipe,
        )
        result = json.loads(_sync_get_todays_menu("alice"))
        assert result["date"] == today.isoformat()
        assert result["menu_name"] == "Weekly"
        assert result["day_of_week"] == DAY_NAMES_RU[today.weekday()]
        assert len(result["meals"]) == 1

    def test_valid_user_empty_menu(self):
        result = json.loads(_sync_get_todays_menu("alice"))
        assert result["meals"] == []
        assert result["menu_name"] == "Weekly"


class SyncGetWeekMenuTests(TestCase):
    """Test _sync_get_week_menu."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@test.com")
        self.menu = Menu.objects.create(user=self.user, name="Weekly")
        UserActiveMenu.objects.create(user=self.user, menu=self.menu)

    def test_user_not_found_returns_error(self):
        result = json.loads(_sync_get_week_menu("nonexistent"))
        assert "error" in result

    def test_valid_user_returns_seven_days(self):
        result = json.loads(_sync_get_week_menu("alice"))
        assert result["menu_name"] == "Weekly"
        assert len(result["days"]) == 7
        day_names = [d["day_of_week"] for d in result["days"]]
        assert day_names == list(DAY_NAMES_RU)


class SyncGetShoppingListTests(TestCase):
    """Test _sync_get_shopping_list."""

    def setUp(self):
        self.user = User.objects.create_user(username="alice", email="alice@test.com")
        self.menu = Menu.objects.create(user=self.user, name="Weekly")
        UserActiveMenu.objects.create(user=self.user, menu=self.menu)
        self.tomato = Ingredient.objects.create(
            user=self.user, name="Tomato", calories=18
        )
        self.recipe = Recipe.objects.create(
            user=self.user, name="Salad", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.tomato, weight_grams=100
        )

    def test_user_not_found_returns_error(self):
        result = json.loads(_sync_get_shopping_list("nonexistent"))
        assert "error" in result

    def test_invalid_date_format_returns_error(self):
        result = json.loads(_sync_get_shopping_list("alice", start_date="not-a-date"))
        assert "error" in result
        assert "date format" in result["error"].lower() or "Invalid" in result["error"]

    def test_people_count_below_one_returns_error(self):
        result = json.loads(_sync_get_shopping_list("alice", people_count=0))
        assert "error" in result
        assert "people_count" in result["error"]

    def test_people_count_above_hundred_returns_error(self):
        result = json.loads(_sync_get_shopping_list("alice", people_count=101))
        assert "error" in result
        assert "people_count" in result["error"]

    def test_date_range_exceeds_ninety_days_returns_error(self):
        start = "2025-01-01"
        end = "2025-06-01"
        result = json.loads(
            _sync_get_shopping_list("alice", start_date=start, end_date=end)
        )
        assert "error" in result
        assert "90" in result["error"]

    def test_valid_call_returns_items(self):
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=self.recipe,
        )
        result = json.loads(
            _sync_get_shopping_list(
                "alice",
                start_date=today.isoformat(),
                end_date=today.isoformat(),
                people_count=1,
            )
        )
        assert result["menu_name"] == "Weekly"
        assert result["people_count"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Tomato"
        assert result["items"][0]["weight_grams"] == 100

    def test_default_dates_uses_today_to_today_plus_six(self):
        result = json.loads(_sync_get_shopping_list("alice"))
        today = date.today()
        assert result["start_date"] == today.isoformat()
        assert result["end_date"] == (today + timedelta(days=6)).isoformat()

    def test_people_count_validation_checked_before_user_lookup(self):
        result = json.loads(_sync_get_shopping_list("nonexistent", people_count=0))
        assert "people_count" in result["error"]


@override_settings(MCP_AUTH_TOKEN="test-secret-token")
class BearerAuthMiddlewareTests(TestCase):
    """Test _AuthMiddleware via Starlette test client."""

    def _get_client(self):
        app = _build_app()
        return TestClient(app, raise_server_exceptions=False)

    def test_missing_authorization_header_returns_401(self):
        client = self._get_client()
        response = client.get("/mcp/")
        assert response.status_code == 401

    def test_wrong_token_returns_401(self):
        client = self._get_client()
        response = client.get("/mcp/", headers={"Authorization": "Bearer wrong-token"})
        assert response.status_code == 401

    @override_settings(MCP_AUTH_TOKEN="test-secret-token")
    def test_correct_token_passes_through(self):
        client = self._get_client()
        response = client.post(
            "/mcp/",
            headers={"Authorization": "Bearer test-secret-token"},
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
        )
        assert response.status_code != 401

    @override_settings(MCP_AUTH_TOKEN="")
    def test_empty_token_setting_always_returns_401(self):
        client = self._get_client()
        response = client.get("/mcp/", headers={"Authorization": "Bearer "})
        assert response.status_code == 401

    @override_settings(MCP_AUTH_TOKEN="")
    def test_empty_token_no_header_returns_401(self):
        client = self._get_client()
        response = client.get("/mcp/")
        assert response.status_code == 401


class OAuth2MetadataTests(TestCase):
    """Test OAuth2 metadata endpoints."""

    def _get_client(self):
        app = _build_app()
        return TestClient(app, raise_server_exceptions=False)

    def test_authorization_server_metadata_returns_correct_structure(self):
        client = self._get_client()
        response = client.get("/.well-known/oauth-authorization-server")
        assert response.status_code == 200
        data = response.json()
        assert "issuer" in data
        assert "token_endpoint" in data
        assert data["grant_types_supported"] == ["client_credentials"]
        assert data["token_endpoint_auth_methods_supported"] == ["client_secret_post"]
        assert data["response_types_supported"] == []
        assert data["token_endpoint"].endswith("/token")

    def test_protected_resource_metadata_returns_correct_structure(self):
        client = self._get_client()
        response = client.get("/.well-known/oauth-protected-resource")
        assert response.status_code == 200
        data = response.json()
        assert "resource" in data
        assert "authorization_servers" in data
        assert isinstance(data["authorization_servers"], list)
        assert len(data["authorization_servers"]) == 1

    def test_metadata_endpoints_accessible_without_auth(self):
        client = self._get_client()
        r1 = client.get("/.well-known/oauth-authorization-server")
        r2 = client.get("/.well-known/oauth-protected-resource")
        assert r1.status_code == 200
        assert r2.status_code == 200


@override_settings(
    MCP_OAUTH_CLIENT_ID="test-client",
    MCP_OAUTH_CLIENT_SECRET="test-secret",
)
class OAuth2TokenEndpointTests(TestCase):
    """Test OAuth2 token endpoint."""

    def _get_client(self):
        app = _build_app()
        return TestClient(app, raise_server_exceptions=False)

    def test_valid_credentials_returns_token(self):
        client = self._get_client()
        response = client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "Bearer"
        assert "expires_in" in data

    def test_invalid_client_id_returns_401(self):
        client = self._get_client()
        response = client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "wrong-client",
                "client_secret": "test-secret",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_client"

    def test_invalid_client_secret_returns_401(self):
        client = self._get_client()
        response = client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "test-client",
                "client_secret": "wrong-secret",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_client"

    def test_unsupported_grant_type_returns_400(self):
        client = self._get_client()
        response = client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert response.status_code == 400
        assert response.json()["error"] == "unsupported_grant_type"

    def test_missing_fields_returns_400(self):
        client = self._get_client()
        response = client.post("/token", data={})
        assert response.status_code == 400

    def test_get_method_not_allowed(self):
        client = self._get_client()
        response = client.get("/token")
        assert response.status_code in (404, 405)

    @override_settings(MCP_OAUTH_CLIENT_ID="", MCP_OAUTH_CLIENT_SECRET="")
    def test_empty_oauth_settings_returns_401(self):
        client = self._get_client()
        response = client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_client"


@override_settings(
    MCP_AUTH_TOKEN="legacy-token",
    MCP_OAUTH_CLIENT_ID="test-client",
    MCP_OAUTH_CLIENT_SECRET="test-secret",
)
class AuthMiddlewareOAuthTests(TestCase):
    """Test _AuthMiddleware with OAuth2 tokens."""

    def _get_client(self):
        app = _build_app()
        return TestClient(app, raise_server_exceptions=False)

    def test_legacy_bearer_token_still_works(self):
        client = self._get_client()
        response = client.post(
            "/mcp/",
            headers={"Authorization": "Bearer legacy-token"},
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
        )
        assert response.status_code != 401

    def test_oauth_token_works(self):
        client = self._get_client()
        token_response = client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        access_token = token_response.json()["access_token"]
        response = client.post(
            "/mcp/",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"jsonrpc": "2.0", "method": "initialize", "id": 1},
        )
        assert response.status_code != 401

    @override_settings(MCP_OAUTH_TOKEN_TTL=0)
    def test_expired_oauth_token_returns_401(self):
        client = self._get_client()
        token_response = client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        access_token = token_response.json()["access_token"]
        response = client.get(
            "/mcp/",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 401

    def test_garbage_jwt_returns_401(self):
        client = self._get_client()
        response = client.get(
            "/mcp/",
            headers={"Authorization": "Bearer not.a.valid.jwt.at.all"},
        )
        assert response.status_code == 401

    def test_no_auth_returns_401_with_www_authenticate(self):
        client = self._get_client()
        response = client.get("/mcp/")
        assert response.status_code == 401
        assert response.headers.get("www-authenticate") == "Bearer"

    def test_public_paths_skip_auth(self):
        client = self._get_client()
        r1 = client.get("/.well-known/oauth-authorization-server")
        r2 = client.get("/.well-known/oauth-protected-resource")
        r3 = client.post(
            "/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert r1.status_code != 401
        assert r2.status_code != 401
        assert r3.status_code != 401
