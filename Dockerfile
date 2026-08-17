# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --create-home app

# Install third-party dependencies in a cacheable layer before copying application code.
COPY pyproject.toml ./
RUN touch README.md \
    && mkdir app \
    && touch app/__init__.py \
    && python -m pip install . \
    && rm -rf app README.md

COPY README.md ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN python -m pip install --no-deps . \
    && mkdir -p /app/storage/audio /home/app/.cache/huggingface \
    && chown -R app:app /app/storage /home/app/.cache

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
