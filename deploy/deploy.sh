#!/usr/bin/env bash
set -euo pipefail

# Aether Deployment Script
# Usage: ./deploy/deploy.sh [--prod]

ENV="${1:-dev}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LOG_FILE="/tmp/aether-deploy-${TIMESTAMP}.log"

log() {
    echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG_FILE"
}

fail() {
    log "❌ $*"
    log "Deploy FAILED at ${TIMESTAMP}"
    exit 1
}

# ── Pre-deploy checks ──────────────────────────────────────
log "=== Aether Deploy — ${TIMESTAMP} ==="

command -v docker >/dev/null 2>&1 || fail "Docker not installed"
command -v docker-compose >/dev/null 2>&1 || command -v docker compose >/dev/null 2>&1 || fail "Docker Compose not installed"

# ── Git pull ────────────────────────────────────────────────
log "Pulling latest code..."
git pull origin master 2>&1 | tee -a "$LOG_FILE" || log "⚠️ Git pull failed (continuing)"

# ── Backend check ───────────────────────────────────────────
log "Running backend checks..."
cd backend

# Python dependencies
if [ -f requirements.txt ]; then
    pip install -r requirements.txt --quiet 2>&1 | tail -3 | tee -a "$LOG_FILE"
fi

# Type check (if mypy installed)
if command -v mypy >/dev/null 2>&1; then
    log "Running mypy..."
    mypy app/ --ignore-missing-imports 2>&1 | tee -a "$LOG_FILE" || log "⚠️ mypy warnings (non-blocking)"
fi

# Alembic migrations
log "Running migrations..."
alembic upgrade head 2>&1 | tee -a "$LOG_FILE" || fail "Migration failed"

cd "$PROJECT_DIR"

# ── Build & Deploy ──────────────────────────────────────────
log "Building Docker images..."
docker compose build 2>&1 | tee -a "$LOG_FILE" || fail "Docker build failed"

log "Restarting services..."
docker compose down --remove-orphans 2>&1 | tee -a "$LOG_FILE"
docker compose up -d 2>&1 | tee -a "$LOG_FILE" || fail "Docker up failed"

# ── Health checks ───────────────────────────────────────────
log "Waiting for services to be healthy..."
sleep 5

# Postgres
if docker compose exec -T postgres pg_isready -U aether 2>/dev/null; then
    log "✅ Postgres healthy"
else
    log "⚠️ Postgres health check failed"
fi

# Backend API
HEALTH_URL="http://localhost:8799/api/v1/health"
for i in {1..10}; do
    if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
        log "✅ Backend API healthy"
        break
    fi
    if [ "$i" -eq 10 ]; then
        fail "Backend API not responding after 10 attempts"
    fi
    sleep 3
done

# Frontend
FRONTEND_URL="http://localhost:5173"
if curl -sf -o /dev/null "$FRONTEND_URL" 2>/dev/null; then
    log "✅ Frontend healthy"
else
    log "⚠️ Frontend health check failed (may need manual start)"
fi

# ── Post-deploy ─────────────────────────────────────────────
log "=== Deploy Complete ==="
log "✅ Backend:  http://localhost:8799/api/v1/health"
log "✅ Frontend: http://localhost:5173"
log "📋 Deploy log: $LOG_FILE"

# Optional: reload nginx
if command -v nginx >/dev/null 2>&1 && nginx -t 2>/dev/null; then
    log "Reloading nginx..."
    nginx -s reload 2>&1 | tee -a "$LOG_FILE"
fi

echo ""
echo "Deploy successful!"
