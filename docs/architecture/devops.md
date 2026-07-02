# 📁 DevOps — Инфраструктура, CI/CD, Мониторинг

Инфраструктура Aether: Docker Compose (dev) → GitHub Actions (CI) → Deploy (production).

**Принцип:** Воспроизводимость. Одна команда — и полное окружение поднято. CI проверяет всё до мёрджа. Production deploy — одна команда с health checks.

---

## 📊 Обзор

```
aether/
├── docker-compose.yml               # Dev-окружение (4 сервиса)
├── docker-compose-new.yml           # Production compose
├── backend-only.yml                 # Только PG + Redis (для работы над бэкендом отдельно)
├── simple-compose.yml               # Минимальный compose
├── full-compose.yml                 # Всё включая Celery workers
├── Makefile                         # dev, test, lint, seed, docker-up/down
├── start.sh                         # Быстрый старт
├── .github/workflows/
│   ├── ci.yml                       # PR checks: lint + test + build
│   └── deploy.yml                   # Push main → SSH deploy на сервер
├── deploy/
│   ├── deploy.sh                    # Скрипт деплоя (git pull → check → docker build → up → health)
│   ├── certbot-init.sh              # SSL-сертификаты через Let's Encrypt
│   └── nginx/                       # Nginx конфиги
├── .pre-commit-config.yaml          # Pre-commit хуки (ruff, mypy, trailing-whitespace, etc.)
└── .env.template                    # Шаблон .env для продакшена
```

---

## 1. Docker Compose — сервисы

### Dev (`docker-compose.yml`)

| Сервис | Образ | Порт | Назначение |
|--------|-------|------|------------|
| `postgres` | `postgres:16-alpine` | `5432` | База данных |
| `redis` | `redis:7-alpine` | `6379` | Кэш, Celery broker, rate limiting |
| `backend` | `backend/Dockerfile` | `8000` | FastAPI (продакшн-режим) |
| `frontend` | `frontend/Dockerfile` (dev target) | `5173` | Vite dev server с HMR |

**Health checks:**
- Postgres: `pg_isready -U aether` (interval 5s, retries 5)
- Redis: `redis-cli ping` (interval 5s, retries 5)
- Backend: `/api/v1/health` (зависит от postgres healthy + redis healthy)
- Frontend: зависит от backend

**Volumes:**
- `postgres_data` — персистентное хранение БД
- `redis_data` — персистентный кэш
- `./aether/docs/specs/schema.sql` → `/docker-entrypoint-initdb.d/01-schema.sql` (авто-инициализация схемы)

### Production (`docker-compose-new.yml`)

Добавляет относительно dev:
- Celery worker + Celery beat
- Nginx reverse proxy с SSL
- Настоящие секреты (не `aether_dev`)
- Ограничения ресурсов (CPU/memory limits)
- `restart: always` на всех сервисах
- PG + Redis без открытых портов наружу (только internal network)

---

## 2. Makefile — команды разработчика

```makefile
make dev              # Запуск backend + frontend в tmux панелях
make dev-backend      # Только backend (uvicorn :8799 --reload)
make dev-frontend     # Только frontend (vite :5173 --host)
make build            # Production сборка фронтенда
make test             # pytest -v --tb=short
make lint             # ruff (backend) + eslint (frontend)
make seed             # Наполнение тестовыми данными
make docker-up        # PG + Redis контейнеры (без backend/frontend)
make docker-down      # Остановка всех контейнеров
make docker-up-all    # Полный стек в Docker
make clean            # Очистка dist + __pycache__
```

---

## 3. CI/CD Pipeline

### CI (`ci.yml`) — запускается на PR/push в main

```yaml
jobs:
  lint:    # ruff check + ruff format --check
  test:    # pytest (PostgreSQL service container, AETHER_ENVIRONMENT=test)
```

**Тестовое окружение:**
- PostgreSQL 16 service container (`aether_test` / `aether_test`)
- Переменные: `AETHER_ENVIRONMENT=test`, JWT secret для тестов
- `pip install -e ".[dev]"` — установка всех dev-зависимостей

### Deploy (`deploy.yml`) — запускается на push в main/master

```yaml
jobs:
  test:     # Полный прогон тестов (PG + Redis service containers)
            # + npm ci + npm run build (проверка сборки фронтенда)
  deploy:   # SSH на сервер → deploy/deploy.sh --prod
            # if: github.ref == 'refs/heads/master' || github.ref == 'refs/heads/main'
```

**Deploy secrets (GitHub Actions Secrets):**
- `DEPLOY_HOST` — IP/домен сервера
- `DEPLOY_USER` — SSH пользователь
- `DEPLOY_SSH_KEY` — Приватный SSH ключ

---

## 4. Pre-commit хуки

Файл `.pre-commit-config.yaml` — запускается при `git commit` (после `pre-commit install`):

| Хук | Инструмент | Проверка |
|-----|-----------|----------|
| trailing-whitespace | pre-commit-hooks | Убирает пробелы в конце строк |
| end-of-file-fixer | pre-commit-hooks | Добавляет пустую строку в конец файла |
| check-yaml/json/toml | pre-commit-hooks | Валидация синтаксиса |
| check-added-large-files | pre-commit-hooks | Запрет файлов >500 KB |
| detect-private-key | pre-commit-hooks | Запрет коммита приватных ключей |
| check-merge-conflict | pre-commit-hooks | Запрет незарешённых конфликтов |
| no-commit-to-branch | pre-commit-hooks | Запрет прямого коммита в main/master |
| ruff (lint) | ruff | Линтинг Python (--fix) |
| ruff-format | ruff | Форматирование Python |
| mypy | mypy | Статическая типизация Python |

**Установка:** `pip install pre-commit && pre-commit install`

---

## 5. Deploy flow (продакшн)

```
Developer push to main
        │
        ▼
  GitHub Actions: deploy.yml
        │
        ├── 1. test job (pytest + frontend build)
        │      └── Упал → deploy отменён
        │
        └── 2. deploy job (SSH to server)
               │
               ├── cd /home/den/.openclaw/workspace/aether
               ├── ./deploy/deploy.sh --prod
               │     ├── git pull origin master
               │     ├── pip install -r requirements.txt
               │     ├── mypy (warnings = non-blocking)
               │     ├── alembic upgrade head
               │     ├── docker compose build
               │     ├── docker compose down --remove-orphans
               │     ├── docker compose up -d
               │     └── Health checks:
               │           ├── pg_isready
               │           ├── curl /api/v1/health (10 retries × 3s)
               │           └── curl frontend :5173
               │
               └── nginx -s reload (если nginx установлен)
```

### SSL-сертификаты

`deploy/certbot-init.sh`:
- Запрашивает Let's Encrypt сертификат через webroot
- Обновляет nginx конфиг с реальным доменом
- Добавляет cron на авто-продление (daily 3 AM)

---

## 6. Переменные окружения

Шаблон `.env.template`:

| Переменная | Назначение | Пример dev |
|-----------|-----------|------------|
| `AETHER_DATABASE_URL` | PostgreSQL DSN | `postgresql+asyncpg://aether:***@localhost:5432/aether` |
| `AETHER_REDIS_URL` | Redis DSN | `redis://localhost:6379/0` |
| `AETHER_JWT_SECRET_KEY` | Секрет для JWT подписи | `dev-secret-change-in-production` |
| `AETHER_JWT_ALGORITHM` | Алгоритм JWT | `HS256` |
| `AETHER_ENCRYPTION_KEY` | Ключ шифрования (AES-256-GCM) | 32-байтовая строка |
| `AETHER_ENVIRONMENT` | `development` / `test` / `production` | `development` |
| `AETHER_CORS_ORIGINS` | JSON-массив разрешённых origin'ов | `["http://localhost:5173"]` |
| `AETHER_ENCRYPTION_KEY` | 32-байтовый ключ для AES-256-GCM | — |

---

## 7. Мониторинг и алертинг (Stage 4)

План на production:

### Health endpoints
- `GET /api/v1/health` — БД + Redis + Celery статус
- `GET /api/v1/admin/health` (admin only) — driver status, очередь задач, usage

### Метрики (Prometheus)
- `request_duration_seconds` — гистограмма latency по эндпоинтам
- `request_count_total` — счётчик запросов (по статусу, tenant'у)
- `active_connections` — активные WebSocket сессии
- `celery_tasks_total` — задачи (completed/failed/retried)
- `ai_inference_duration_seconds` — latency inference по драйверам
- `billing_credits_consumed` — потребление токенов

### Logging
- Структурированные логи в JSON (ELK-ready)
- Уровни: DEBUG (dev), INFO (prod), ERROR (always)
- `X-Request-ID` заголовок для трассировки запросов
- Контекст в каждом логе: `tenant_id`, `user_id`, `request_id`

### Алерты (Stage 4)
- API latency >2s (P95) → Telegram
- Error rate >5% за 5 мин → Telegram
- DB connections >80% пула → Telegram
- Free disk <10% → Telegram
- Celery queue depth >100 → Telegram

---

## 8. Бэкапы (Stage 4)

- **PostgreSQL:** `pg_dump` nightly в `/backups/aether/` + S3
- **Redis:** RDB snapshot каждый час (если нужна персистентность кэша)
- **Retention:** 7 daily + 4 weekly + 3 monthly
- **Restore test:** ежемесячный restore в изолированное окружение

---

## 🤖 Для агентов

При изменении инфраструктуры:
1. Обнови соответствующий Dockerfile / compose-файл
2. Проверь что CI проходит (`make test && make lint`)
3. Обнови этот документ если меняется архитектура деплоя
4. `.env.template` — добавить новые переменные, если появились
