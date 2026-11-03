#!/bin/sh
set -e
echo "Migratsiyalar: alembic upgrade head"
alembic upgrade head
echo "Boshlang'ich ma'lumotlar (idempotent)"
python -m app.seed
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
