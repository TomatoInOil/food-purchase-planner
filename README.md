# food-purchase-planner

Планировщик покупок и менеджер рецептов. Главная страница доступна после входа; есть регистрация (`/register/`), вход (`/login/`) и выход (`/logout/`).

## Развёртывание

### Локально (без Docker)

1. Установить зависимости: `uv sync`
2. Применить миграции: `uv run python src/manage.py migrate`
3. (опционально) Заполнить ингредиенты по умолчанию: `uv run python src/manage.py planner_populate_default_ingredients`; затем рецепты: `uv run python src/manage.py planner_populate_default_recipes`
4. Из корня проекта: `uv run python src/manage.py runserver`
5. Открыть в браузере: http://127.0.0.1:8000/

### Docker (PostgreSQL + Nginx Proxy Manager)

1. Скопировать `.env.example` в `.env` и задать `POSTGRES_PASSWORD` (и при необходимости `SECRET_KEY`, `ALLOWED_HOSTS`).
2. Запустить: `docker compose up -d`
3. Первый вход в NPM: http://localhost:81 — создать Proxy Host: Forward Hostname/IP = `web`, Port = `8000`. Для SSL: вкладка SSL → Request New Certificate.
4. Для раздачи статики Django в NPM: в Proxy Host добавить Custom location: `/static` → `/data/static` (volume уже смонтирован).
5. Переменные для прода: задать `SECRET_KEY`, `ALLOWED_HOSTS` (через `.env` или окружение).

### Администрирование (Docker)

- **Логи:** `docker compose logs -f` — все сервисы; `docker compose logs -f web` — только приложение.
- **Management-команды:** кастомные (скопировать и выполнить):
  - `docker compose exec web python manage.py planner_populate_default_ingredients`
  - `docker compose exec web python manage.py planner_populate_default_recipes`
- **Перезапуск:** `docker compose restart web`; полная пересборка: `docker compose up -d --build`.
