#!/bin/sh

set -e

echo "⏳ Waiting for database..."

until pg_isready -h db -p 5432 -U triageiq -d triageiq; do
  sleep 1
done

echo "✅ Database is ready"

echo "🚀 Running migrations..."
alembic upgrade head

echo "🔥 Starting API..."
# exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
