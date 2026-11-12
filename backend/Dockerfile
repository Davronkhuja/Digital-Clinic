FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# PDF uchun Unicode shrift (kirill va lotin): DejaVu
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# --- test: pytest va ruff bilan (docker compose --profile test run --rm test) ---
FROM base AS test
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["pytest"]

# --- runtime (standart; compose target: runtime) ---
FROM base AS runtime
RUN useradd -r -u 1001 appuser && mkdir -p /data/uploads && chown -R appuser /app /data/uploads
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

CMD ["./entrypoint.sh"]
