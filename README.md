# food-purchase-planner

Планировщик покупок и менеджер рецептов. Главная страница доступна после входа; есть регистрация (`/register/`), вход (`/login/`) и выход (`/logout/`).

## Развёртывание

1. Установить зависимости: `uv sync`
2. Применить миграции: `uv run python src/manage.py migrate`
3. (опционально) Заполнить ингредиенты по умолчанию: `uv run python src/manage.py planner_populate_default_ingredients`
4. Из корня проекта: `uv run python src/manage.py runserver`
5. Открыть в браузере: http://127.0.0.1:8000/