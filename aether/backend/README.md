# Aether Backend

FastAPI-based multi-tenant SaaS backend.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your database URL, secrets, etc.

# 3. Run database migrations
alembic upgrade head

# 4. Start the server
uvicorn app.main:app --reload --port 8000
```

## Health Check

```bash
curl http://localhost:8000/api/v1/health
```

## Docker

```bash
docker build -t aether-backend .
docker run -p 8000:8000 --env-file .env aether-backend
```

## Project Structure

```
app/
├── main.py           # FastAPI app, lifespan, CORS
├── config.py         # Pydantic Settings (env vars + .env)
├── database.py       # Async SQLAlchemy engine + session
├── dependencies.py   # DI (get_db, get_current_user stub)
├── api/
│   ├── router.py     # Main v1 router
│   └── v1/
│       └── health.py # Health check endpoint
├── core/
│   └── security.py   # Password hashing, JWT, API keys
├── middleware/
│   ├── tenant.py     # Tenant context (ContextVar + header)
│   └── logging.py    # Request logging
├── models/           # SQLAlchemy models
└── schemas/          # Pydantic request/response schemas
```
