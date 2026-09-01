FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY voltdesk ./voltdesk
COPY schemas ./schemas
RUN pip install -e .

COPY scripts ./scripts
COPY migrations ./migrations
COPY data ./data

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://localhost:8000/health/live || exit 1

CMD ["uvicorn", "voltdesk.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
