"""MCP server exposing menu and shopping list tools via Streamable HTTP."""

import hmac
import json
import logging
import os
import secrets
import time
from datetime import date, timedelta

import jwt
import uvicorn

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from asgiref.sync import sync_to_async  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402
from starlette.routing import Route  # noqa: E402
from starlette.types import ASGIApp  # noqa: E402

from planner.models import MenuSlot  # noqa: E402
from planner.services import calculate_shopping_list, get_active_menu  # noqa: E402

logger = logging.getLogger(__name__)

User = get_user_model()

DAY_NAMES_RU = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]

MEAL_TYPE_NAMES_RU = {
    0: "Завтрак",
    1: "Обед",
    2: "Перекус",
    3: "Ужин",
}

mcp = FastMCP("Food Purchase Planner")

_MCP_JWT_ISSUER = "food-purchase-planner"
_MCP_JWT_AUDIENCE = "food-purchase-planner-mcp"

_OAUTH_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-protected-resource",
        "/token",
    }
)


def _get_user(username: str):
    """Look up a user by username. Returns User or error string."""
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


def _build_recipe_data(recipe) -> dict:
    """Build recipe dict with ingredients and nutrition."""
    ingredients = [
        {"name": ri.ingredient.name, "weight_grams": ri.weight_grams}
        for ri in recipe.recipe_ingredients.select_related("ingredient").all()
    ]
    return {
        "name": recipe.name,
        "description": recipe.description or "",
        "instructions": recipe.instructions or "",
        "ingredients": ingredients,
        "nutrition": {
            "calories": recipe.total_calories,
            "protein": recipe.total_protein,
            "fat": recipe.total_fat,
            "carbs": recipe.total_carbs,
        },
    }


def _build_day_data(menu, day_of_week: int) -> dict:
    """Build day data with meals for a given day_of_week."""
    today = date.today()
    days_ahead = day_of_week - today.weekday()
    if days_ahead < 0:
        days_ahead += 7
    target_date = today + timedelta(days=days_ahead)

    slots = (
        MenuSlot.objects.filter(menu=menu, day_of_week=day_of_week)
        .exclude(recipe__isnull=True)
        .select_related("recipe")
        .order_by("meal_type")
    )

    meals_by_type: dict[int, list[dict]] = {}
    for slot in slots:
        recipe_data = _build_recipe_data(slot.recipe)
        recipe_data["servings"] = slot.servings
        meals_by_type.setdefault(slot.meal_type, []).append(recipe_data)

    meals = []
    for meal_type in sorted(meals_by_type.keys()):
        meals.append(
            {
                "meal_type": MEAL_TYPE_NAMES_RU[meal_type],
                "recipes": meals_by_type[meal_type],
            }
        )

    return {
        "date": target_date.isoformat(),
        "day_of_week": DAY_NAMES_RU[day_of_week],
        "meals": meals,
    }


def _sync_get_todays_menu(username: str) -> str:
    """Synchronous implementation of get_todays_menu."""
    user = _get_user(username)
    if user is None:
        return json.dumps({"error": f"User '{username}' not found"}, ensure_ascii=False)

    menu = get_active_menu(user)
    today = date.today()
    day_of_week = today.weekday()

    day_data = _build_day_data(menu, day_of_week)
    day_data["date"] = today.isoformat()
    day_data["menu_name"] = menu.name

    return json.dumps(day_data, ensure_ascii=False)


def _sync_get_week_menu(username: str) -> str:
    """Synchronous implementation of get_week_menu."""
    user = _get_user(username)
    if user is None:
        return json.dumps({"error": f"User '{username}' not found"}, ensure_ascii=False)

    menu = get_active_menu(user)
    days = []
    for day_of_week in range(7):
        days.append(_build_day_data(menu, day_of_week))

    result = {
        "menu_name": menu.name,
        "days": days,
    }
    return json.dumps(result, ensure_ascii=False)


def _sync_get_shopping_list(
    username: str,
    start_date: str | None = None,
    end_date: str | None = None,
    people_count: int = 2,
) -> str:
    """Synchronous implementation of get_shopping_list."""
    if people_count < 1 or people_count > 100:
        return json.dumps(
            {"error": "people_count must be between 1 and 100"}, ensure_ascii=False
        )

    user = _get_user(username)
    if user is None:
        return json.dumps({"error": f"User '{username}' not found"}, ensure_ascii=False)

    menu = get_active_menu(user)

    today = date.today()
    try:
        parsed_start = date.fromisoformat(start_date) if start_date else today
        parsed_end = (
            date.fromisoformat(end_date) if end_date else today + timedelta(days=6)
        )
    except ValueError:
        return json.dumps(
            {"error": "Invalid date format, expected YYYY-MM-DD"}, ensure_ascii=False
        )

    if (parsed_end - parsed_start).days > 90:
        return json.dumps(
            {"error": "Date range must not exceed 90 days"}, ensure_ascii=False
        )

    items = calculate_shopping_list(menu, parsed_start, parsed_end, people_count)
    result = {
        "menu_name": menu.name,
        "start_date": parsed_start.isoformat(),
        "end_date": parsed_end.isoformat(),
        "people_count": people_count,
        "items": items,
    }
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
async def get_todays_menu(username: str) -> str:
    """Get today's menu for a user from their active weekly menu plan."""
    return await sync_to_async(_sync_get_todays_menu)(username)


@mcp.tool()
async def get_week_menu(username: str) -> str:
    """Get the full weekly menu for a user from their active menu plan."""
    return await sync_to_async(_sync_get_week_menu)(username)


@mcp.tool()
async def get_shopping_list(
    username: str,
    start_date: str | None = None,
    end_date: str | None = None,
    people_count: int = 2,
) -> str:
    """Get an aggregated shopping list for a user's active menu over a date range."""
    return await sync_to_async(_sync_get_shopping_list)(
        username, start_date, end_date, people_count
    )


def _generate_access_token(client_id: str) -> tuple[str, int]:
    """Generate a JWT access token for the given client."""
    now = int(time.time())
    ttl = settings.MCP_OAUTH_TOKEN_TTL
    payload = {
        "iss": _MCP_JWT_ISSUER,
        "aud": _MCP_JWT_AUDIENCE,
        "sub": client_id,
        "iat": now,
        "exp": now + ttl,
        "jti": secrets.token_hex(16),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return token, ttl


def _validate_access_token(token: str) -> bool:
    """Validate a JWT access token. Returns True if valid."""
    try:
        jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            issuer=_MCP_JWT_ISSUER,
            audience=_MCP_JWT_AUDIENCE,
        )
        return True
    except jwt.InvalidTokenError:
        return False
    except Exception:
        logger.exception("Unexpected error validating access token")
        return False


class _AuthMiddleware(BaseHTTPMiddleware):
    """Check Bearer token or OAuth2 JWT for MCP endpoints."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.url.path in _OAUTH_PUBLIC_PATHS:
            response: Response = await call_next(request)
            return response

        auth_header = request.headers.get("authorization", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        if (
            token
            and settings.MCP_AUTH_TOKEN
            and hmac.compare_digest(token, settings.MCP_AUTH_TOKEN)
        ):
            response = await call_next(request)
            return response

        if token and _validate_access_token(token):
            response = await call_next(request)
            return response

        logger.warning("Auth failed for %s %s", request.method, request.url.path)
        return JSONResponse(
            {"error": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _handle_token_request(request: Request) -> Response:
    """Handle OAuth2 client_credentials token request."""
    form_data = await request.form()
    grant_type = form_data.get("grant_type", "")
    if grant_type != "client_credentials":
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

    client_id = form_data.get("client_id", "")
    client_secret = form_data.get("client_secret", "")

    expected_id = settings.MCP_OAUTH_CLIENT_ID
    expected_secret = settings.MCP_OAUTH_CLIENT_SECRET

    if (
        not expected_id
        or not expected_secret
        or not hmac.compare_digest(str(client_id), expected_id)
        or not hmac.compare_digest(str(client_secret), expected_secret)
    ):
        logger.warning("OAuth2 token request with invalid client credentials")
        return JSONResponse({"error": "invalid_client"}, status_code=401)

    token, ttl = _generate_access_token(str(client_id))
    return JSONResponse(
        {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": ttl,
        }
    )


async def _handle_authorization_server_metadata(request: Request) -> Response:
    """Return OAuth2 authorization server metadata."""
    issuer = f"{request.url.scheme}://{request.url.netloc}"
    return JSONResponse(
        {
            "issuer": issuer,
            "token_endpoint": f"{issuer}/token",
            "grant_types_supported": ["client_credentials"],
            "token_endpoint_auth_methods_supported": ["client_secret_post"],
            "response_types_supported": [],
        }
    )


async def _handle_protected_resource_metadata(request: Request) -> Response:
    """Return OAuth2 protected resource metadata."""
    resource = f"{request.url.scheme}://{request.url.netloc}"
    return JSONResponse(
        {
            "resource": resource,
            "authorization_servers": [resource],
        }
    )


def _build_app() -> Starlette:
    """Build the Starlette app with MCP routes, OAuth2 endpoints, and auth middleware."""
    mcp_app = mcp.streamable_http_app()
    routes = [
        Route(
            "/.well-known/oauth-authorization-server",
            _handle_authorization_server_metadata,
        ),
        Route(
            "/.well-known/oauth-protected-resource",
            _handle_protected_resource_metadata,
        ),
        Route("/token", _handle_token_request, methods=["POST"]),
        Route("/{path:path}", mcp_app),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(_AuthMiddleware)
    return app


def run_server(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Start the MCP server with Streamable HTTP transport."""
    app = _build_app()
    logger.info("Starting MCP server on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)
