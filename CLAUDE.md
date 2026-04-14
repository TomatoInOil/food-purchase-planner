# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Food Purchase Planner — a Django 6 + DRF application for recipe/meal planning with social features. Russian-language UI. Vanilla JS frontend, PostgreSQL in production (SQLite locally).

## Common Commands

```bash
# Install dependencies
uv sync

# Run dev server
uv run python src/manage.py runserver

# Run all tests
uv run pytest

# Run a single test file
uv run pytest src/planner/tests/test_models.py -v

# Run a single test by name
uv run pytest -k "test_name" -v

# Linting
uv run ruff check src

# Type checking
uv run mypy src

# Apply migrations
uv run python src/manage.py migrate

# Seed data
uv run python src/manage.py planner_populate_default_ingredients
uv run python src/manage.py planner_populate_default_recipes

# Telegram bot
uv run python src/manage.py run_telegram_bot        # start polling bot
uv run python src/manage.py send_telegram_broadcast  # send broadcast to all linked users

# MCP server
MCP_AUTH_TOKEN=test uv run python src/manage.py run_mcp_server
```

Pre-commit hooks run ruff and mypy automatically on commit.

## Architecture

```
src/
├── config/          # Django project config, auth views, templates, static assets (JS/CSS)
└── planner/         # Main app
```

**Backend layers** (in `src/planner/`):
- `models.py` — 9 models: Ingredient, Recipe, RecipeIngredient, Menu, MenuSlot, UserFriendCode, FriendRequest, UserTelegramProfile, TelegramLinkToken
- `serializers.py` — DRF serializers (API contract layer)
- `views_api.py` — DRF ViewSets and API views
- `views_friends.py` — Friend management API views
- `views_telegram.py` — Telegram account linking API views (generate link token, check status)
- `bot.py` — Telegram polling bot (account linking via `/start <token>`)
- `services.py` — Business logic (shopping list aggregation, menu operations)
- `services_friends.py` — Friend relationship logic
- `services_import.py` — Ingredient import from HTML content
- `permissions.py` — Custom DRF permissions (IsOwnerOrReadOnly, IsOwnerOrFriendEditorOrReadOnly)

**Frontend** (`src/config/static/js/`): Vanilla JS modules — `api.js` (fetch wrapper + CSRF), `state.js`, `recipes.js`, `ingredients.js`, `menu.js`, `shopping.js`, `friends.js`, `tabs.js`, `init.js`.

**API prefix**: `/api/` — uses DRF DefaultRouter for ingredients, recipes, friend-requests, plus custom views for menus, shopping-list, and friend operations.

## Key Patterns

- **Nutrient calculation**: Ingredients store per-100g values; `Recipe.recalculate_nutrition()` computes totals from RecipeIngredient weights. Auto-updates on save.
- **Friend sharing**: 8-char alphanumeric codes, bidirectional requests with status workflow (pending/accepted/declined/removed/cancelled), separate permission for recipe editing.
- **"System" user**: An inactive user whose ingredients serve as defaults for all users.
- **Settings**: `config.settings` — reads from `.env` via python-dotenv. See `.env.example` for available variables. Telegram requires `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME`.

## Testing

pytest + pytest-django. Config in `pyproject.toml` sets `DJANGO_SETTINGS_MODULE = "config.settings"` and `pythonpath = "src"`. Tests are in `src/planner/tests/` (test_models, test_api_contract, test_api_edge_cases, test_permissions, test_serializers, test_services, test_signals, test_import, test_config).

## CI/CD

GitHub Actions: lint+test on push/PR to master → build Docker image to ghcr.io → deploy to VDS via SSH + docker-compose.

When adding, removing, or renaming environment variables, update **both** the deploy workflow (`.github/workflows/`) and the `environment` sections in `docker-compose.prod.yml` (`web` and `bot` services) — env vars are passed explicitly to containers in both places. The `.env` file on the host is NOT mounted into containers; variables reach Django only through docker-compose `environment`.
