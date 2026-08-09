#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON="$ROOT_DIR/.venv/bin/python"
UVICORN="$ROOT_DIR/.venv/bin/uvicorn"
ALEMBIC="$ROOT_DIR/.venv/bin/alembic"
BACKEND_URL="http://127.0.0.1:8000"
FRONTEND_URL="http://localhost:3000"

BACKEND_PID=""
FRONTEND_PID=""
OLLAMA_PID=""
STARTUP_COMPLETE=0
LOGS_CREATED=0
LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ai-meeting-assistant.XXXXXX")"

cd "$ROOT_DIR"

error() {
    printf 'Error: %s\n' "$1" >&2
}

process_is_running() {
    local pid="$1"
    local state

    [[ -n "$pid" ]] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    state="$(ps -o stat= -p "$pid" 2>/dev/null || true)"
    [[ "$state" != *Z* ]]
}

stop_process_tree() {
    local pid="$1"
    local child
    local children=""
    local attempt

    [[ "$pid" =~ ^[0-9]+$ ]] || return 0

    if command -v pgrep >/dev/null 2>&1; then
        children="$(pgrep -P "$pid" 2>/dev/null || true)"
        for child in $children; do
            stop_process_tree "$child"
        done
    fi

    kill -TERM "$pid" 2>/dev/null || true
    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        process_is_running "$pid" || break
        sleep 0.2
    done

    if process_is_running "$pid"; then
        kill -KILL "$pid" 2>/dev/null || true
    fi
    wait "$pid" 2>/dev/null || true
}

cleanup() {
    local status=$?

    trap - EXIT INT TERM

    if [[ -n "$FRONTEND_PID" || -n "$BACKEND_PID" || -n "$OLLAMA_PID" ]]; then
        printf '\nStopping AI Meeting Assistant...\n'
    fi

    stop_process_tree "$FRONTEND_PID"
    stop_process_tree "$BACKEND_PID"

    if [[ -n "$OLLAMA_PID" ]]; then
        stop_process_tree "$OLLAMA_PID"
    fi

    if [[ "$status" -eq 0 && "$STARTUP_COMPLETE" -eq 1 ]]; then
        rm -rf -- "$LOG_DIR"
        printf 'Stopped.\n'
    elif [[ "$LOGS_CREATED" -eq 1 ]]; then
        printf 'Startup logs were kept at: %s\n' "$LOG_DIR" >&2
    else
        rm -rf -- "$LOG_DIR"
    fi

    exit "$status"
}

handle_signal() {
    exit 0
}

trap cleanup EXIT
trap handle_signal INT TERM

http_ready() {
    local url="$1"

    "$PYTHON" - "$url" <<'PY' >/dev/null 2>&1
import sys
import urllib.request

request = urllib.request.Request(sys.argv[1], method="GET")
with urllib.request.urlopen(request, timeout=0.75) as response:
    if not 200 <= response.status < 300:
        raise SystemExit(1)
PY
}

wait_for_http() {
    local url="$1"
    local pid="$2"
    local attempts="$3"
    local attempt

    for ((attempt = 1; attempt <= attempts; attempt++)); do
        if http_ready "$url"; then
            return 0
        fi
        if [[ -n "$pid" ]] && ! process_is_running "$pid"; then
            return 1
        fi
        sleep 0.5
    done

    return 1
}

model_is_available() {
    local tags_url="$1"
    local required_model="$2"

    "$PYTHON" - "$tags_url" "$required_model" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
    payload = json.load(response)

available = {
    value
    for model in payload.get("models", [])
    for value in (model.get("name"), model.get("model"))
    if value
}
raise SystemExit(0 if sys.argv[2] in available else 1)
PY
}

if [[ ! -f "$ROOT_DIR/.env" ]]; then
    error "Backend environment file not found. Run: cp .env.example .env"
    exit 1
fi

if [[ ! -x "$PYTHON" || ! -x "$UVICORN" || ! -x "$ALEMBIC" ]]; then
    error "Python virtual environment is incomplete or missing. Run the backend setup in README.md first."
    exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
    error "npm is not installed. Install Node.js 20.9 or newer and try again."
    exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" || ! -x "$FRONTEND_DIR/node_modules/.bin/next" ]]; then
    error "Frontend dependencies not installed. Run: cd frontend && npm install"
    exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
    error "Ollama is not installed. Install Ollama, then follow the setup instructions in README.md."
    exit 1
fi

if ! APP_CONFIG="$("$PYTHON" - <<'PY'
from app.core.config import get_settings

settings = get_settings()
print(settings.ollama_base_url)
print(settings.ollama_analysis_model)
PY
)"; then
    error "Application configuration is invalid. Check .env and try again."
    exit 1
fi

OLLAMA_BASE_URL="$(printf '%s\n' "$APP_CONFIG" | sed -n '1p')"
OLLAMA_MODEL="$(printf '%s\n' "$APP_CONFIG" | sed -n '2p')"
OLLAMA_TAGS_URL="${OLLAMA_BASE_URL%/}/api/tags"

printf 'Checking PostgreSQL...\n'
if ! "$PYTHON" - <<'PY' >/dev/null 2>&1
import asyncio

from sqlalchemy import text

from app.db.session import engine


async def check_database() -> None:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


asyncio.run(asyncio.wait_for(check_database(), timeout=5))
PY
then
    error "PostgreSQL is not reachable. Start PostgreSQL and try again."
    exit 1
fi

printf 'Applying database migrations...\n'
LOGS_CREATED=1
if ! "$ALEMBIC" upgrade head >"$LOG_DIR/alembic.log" 2>&1; then
    error "Database migration failed. See $LOG_DIR/alembic.log"
    exit 1
fi

if ! http_ready "$OLLAMA_TAGS_URL"; then
    printf 'Starting Ollama...\n'
    OLLAMA_HOST="$OLLAMA_BASE_URL" ollama serve >"$LOG_DIR/ollama.log" 2>&1 &
    OLLAMA_PID=$!

    if ! wait_for_http "$OLLAMA_TAGS_URL" "$OLLAMA_PID" 40; then
        error "Ollama did not become ready. See $LOG_DIR/ollama.log"
        exit 1
    fi
else
    printf 'Using the existing Ollama service.\n'
fi

if ! model_is_available "$OLLAMA_TAGS_URL" "$OLLAMA_MODEL"; then
    error "Required Ollama model is not installed. Run: ollama pull $OLLAMA_MODEL"
    exit 1
fi

if http_ready "$BACKEND_URL/health"; then
    error "A backend is already running at $BACKEND_URL. Stop it and try again."
    exit 1
fi

if http_ready "$FRONTEND_URL"; then
    error "A frontend is already running at $FRONTEND_URL. Stop it and try again."
    exit 1
fi

printf 'Starting FastAPI...\n'
"$UVICORN" app.main:app --host 127.0.0.1 --port 8000 >"$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

if ! wait_for_http "$BACKEND_URL/health" "$BACKEND_PID" 40; then
    error "FastAPI did not become ready. See $LOG_DIR/backend.log"
    exit 1
fi

printf 'Starting Next.js...\n'
(
    cd "$FRONTEND_DIR"
    NEXT_PUBLIC_API_BASE_URL="$BACKEND_URL" exec npm run dev -- --hostname 127.0.0.1 --port 3000
) >"$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

if ! wait_for_http "$FRONTEND_URL" "$FRONTEND_PID" 60; then
    error "Next.js did not become ready. See $LOG_DIR/frontend.log"
    exit 1
fi

STARTUP_COMPLETE=1

cat <<EOF

AI Meeting Assistant is ready.

App:      $FRONTEND_URL
API:      $BACKEND_URL
API docs: $BACKEND_URL/docs
Logs:     $LOG_DIR

Press Ctrl+C to stop.
EOF

if [[ "${AI_MEETING_NO_BROWSER:-0}" != "1" ]]; then
    if [[ "$(uname -s)" == "Darwin" ]] && command -v open >/dev/null 2>&1; then
        open "$FRONTEND_URL" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$FRONTEND_URL" >/dev/null 2>&1 || true
    fi
fi

while true; do
    if ! process_is_running "$BACKEND_PID"; then
        error "FastAPI stopped unexpectedly. See $LOG_DIR/backend.log"
        exit 1
    fi
    if ! process_is_running "$FRONTEND_PID"; then
        error "Next.js stopped unexpectedly. See $LOG_DIR/frontend.log"
        exit 1
    fi
    if [[ -n "$OLLAMA_PID" ]] && ! process_is_running "$OLLAMA_PID"; then
        error "Ollama stopped unexpectedly. See $LOG_DIR/ollama.log"
        exit 1
    fi
    sleep 1
done
