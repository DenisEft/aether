# Aether — Development Makefile

.PHONY: dev dev-backend dev-frontend build test lint seed clean docker-up docker-down

# === Development ===

dev:
	@echo "Starting Aether development environment..."
	@tmux new-session -d -s aether 'make dev-backend' \; \
		split-window -h 'make dev-frontend' \; \
		attach
	@echo "Backend: http://localhost:8799 (API), http://localhost:8799/docs (Swagger)"
	@echo "Frontend: http://localhost:5173"

dev-backend:
	cd backend && python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8799 --reload

dev-frontend:
	cd frontend && npx vite --host 0.0.0.0 --port 5173 --strictPort

build:
	cd frontend && npx vite build

# === Testing ===

test:
	cd backend && python3 -m pytest -v --tb=short

lint:
	cd backend && python3 -m ruff check app/
	cd frontend && npx eslint src/ --ext .ts,.vue

# === Seed Data ===

seed:
	cd backend && python3 -m app.seed

# === Docker ===

docker-up:
	docker compose up -d postgres redis

docker-down:
	docker compose down

docker-up-all:
	docker compose up -d --build

# === Cleanup ===

clean:
	rm -rf frontend/dist
	find backend -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
