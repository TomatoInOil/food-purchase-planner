# food-purchase-planner

Планировщик покупок и менеджер рецептов. Главная страница доступна после входа; есть регистрация (`/register/`), вход (`/login/`) и выход (`/logout/`).

## Развёртывание

1. Установить зависимости: `uv sync`
2. Применить миграции: `uv run python src/manage.py migrate`
3. Из корня проекта: `uv run python src/manage.py runserver`
4. Открыть в браузере: http://127.0.0.1:8000/