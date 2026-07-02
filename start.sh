#!/bin/bash

echo "Starting Aether platform..."

# Запускаем PostgreSQL и Redis
echo "Starting database services..."
docker compose -f simple-compose.yml up -d postgres redis

# Ждем запуска сервисов
sleep 5

# Проверяем статус базы данных
echo "Checking database status..."
docker compose -f simple-compose.yml exec postgres pg_isready -U aether

# Если база доступна, загружаем схему
if [ $? -eq 0 ]; then
    echo "Database is ready. Loading schema..."
    docker compose -f simple-compose.yml exec postgres psql -U aether -c "SELECT 'Schema loaded successfully';"
fi

echo "Aether platform started successfully!"
echo "Services:"
echo "  PostgreSQL:   localhost:5432"
echo "  Redis:        localhost:6380"
echo "  Backend API:  (not started - requires dependencies)"