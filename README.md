# food-purchase-planner

Планировщик покупок и менеджер рецептов. Главная страница доступна после входа; есть регистрация (`/register/`), вход (`/login/`) и выход (`/logout/`).

**Стек:** Django 6, Python 3.13. Управление зависимостями — [uv](https://docs.astral.sh/uv/).

## Разработка

- **Зависимости:** `uv sync` (dev-зависимости: pytest, pytest-django, ruff, mypy).
- **Тесты:** `uv run pytest src/planner/tests.py -v` или `uv run python src/manage.py test planner`.
- **Линтеры:** `uv run ruff check src`, `uv run mypy src`.

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

## CI/CD (GitHub Actions)

- **CI - lint & tests:** запускается на push/pull request в ветку `master`, проверяет код Ruff и mypy, запускает Django-тесты.
- **Build and publish Docker image:** запускается автоматически после успешного `CI - lint & tests` для ветки `master`, собирает и публикует образ в `ghcr.io/${{ github.repository }}` с тегами `latest` (для `master`) и `sha-<commit_sha>`.
- **CD - deploy via docker compose:** запускается
  - автоматически по событию `workflow_run` после успешного `Build and publish Docker image` для ветки `master`;
  - вручную через `workflow_dispatch` с параметром `image_tag` (по умолчанию `latest`).

Деплой предполагает VDS с установленными `docker` и `docker compose`, а также клоном этого репозитория (директория на сервере передаётся через секрет `DEPLOY_WORKDIR`). Workflow через `appleboy/ssh-action` подключается по SSH и выполняет на сервере скрипт `./deploy.sh <IMAGE_TAG>`, внутри которого вызываются `docker compose pull` и `docker compose up -d`.

### Секреты и переменные для деплоя

В разделе **Settings → Secrets and variables → Actions** репозитория должны быть заданы:

- `VDS_SSH_HOST` — хост VDS.
- `VDS_SSH_USER` — пользователь для SSH-доступа.
- `VDS_SSH_KEY` — приватный SSH-ключ (формат PEM), с доступом к указанному пользователю/серверу.
- (опционально) `VDS_SSH_PORT` — порт SSH, если отличается от `22`.
- (опционально) `DEPLOY_WORKDIR` — рабочая директория на сервере, где лежит `docker-compose.yml` и скрипт `deploy.sh` (по умолчанию `.`).
- (опционально, но рекомендуется для pull образов с приватного регистра) `GHCR_USER` и `GHCR_TOKEN` — учётные данные для `ghcr.io`. Если заданы, `deploy.sh` выполнит `docker login ghcr.io` перед `docker compose pull`.
- **Обязательные для docker-compose:** `POSTGRES_PASSWORD`, `SECRET_KEY`, `ALLOWED_HOSTS`. В шаге «Deploy via SSH» на сервере формируется файл `.env` из этих секретов перед запуском `deploy.sh`; при отсутствии любого из них шаг «Validate deploy config» завершится с ошибкой. Для production задайте в `ALLOWED_HOSTS` ваш домен (не используйте localhost).
- (опционально) `POSTGRES_USER`, `POSTGRES_DB` — подставляются в `.env` при деплое; по умолчанию используются значения из `.env.example`.
