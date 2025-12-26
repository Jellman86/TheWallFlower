#!/bin/bash
set -e

# TheWallflower Docker Entrypoint
# Handles initialization, signal handling, and graceful shutdown

# Colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Trap signals for graceful shutdown
cleanup() {
    log_info "Received shutdown signal, stopping gracefully..."
    if [ -n "$APP_PID" ]; then
        kill -TERM "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi
    log_info "Shutdown complete"
    exit 0
}

trap cleanup SIGTERM SIGINT SIGQUIT

# Banner
echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║         TheWallflower NVR             ║"
echo "  ║    Self-hosted NVR with Speech-to-Text ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# Environment defaults
export DATABASE_URL="${DATABASE_URL:-sqlite:///data/thewallflower.db}"
export WHISPER_HOST="${WHISPER_HOST:-whisper-live}"
export WHISPER_PORT="${WHISPER_PORT:-9090}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export WORKERS="${WORKERS:-1}"

# Ensure data directory exists
DATA_DIR="${DATA_DIR:-/data}"
if [ ! -d "$DATA_DIR" ]; then
    log_info "Creating data directory: $DATA_DIR"
    mkdir -p "$DATA_DIR"
fi

# Ensure database directory exists
DB_DIR=$(dirname "${DATABASE_URL#sqlite:///}")
if [ "$DB_DIR" != "." ] && [ ! -d "$DB_DIR" ]; then
    log_info "Creating database directory: $DB_DIR"
    mkdir -p "$DB_DIR"
fi

# Log configuration
log_info "Configuration:"
log_info "  DATABASE_URL: $DATABASE_URL"
log_info "  WHISPER_HOST: $WHISPER_HOST"
log_info "  WHISPER_PORT: $WHISPER_PORT"
log_info "  LOG_LEVEL: $LOG_LEVEL"
log_info "  WORKERS: $WORKERS"

# Wait for WhisperLive if configured
if [ "${WAIT_FOR_WHISPER:-false}" = "true" ]; then
    log_info "Waiting for WhisperLive at $WHISPER_HOST:$WHISPER_PORT..."
    MAX_RETRIES=30
    RETRY_COUNT=0
    while ! nc -z "$WHISPER_HOST" "$WHISPER_PORT" 2>/dev/null; do
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
            log_warn "WhisperLive not available after $MAX_RETRIES attempts, continuing anyway"
            break
        fi
        log_info "Waiting for WhisperLive... (attempt $RETRY_COUNT/$MAX_RETRIES)"
        sleep 2
    done
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        log_info "WhisperLive is available"
    fi
fi

# Run database migrations if needed
log_info "Initializing database..."
python -c "from backend.app.db import init_db; init_db()" 2>/dev/null || {
    log_warn "Database initialization will happen on first request"
}

# Start the application
log_info "Starting TheWallflower..."

if [ "$1" = "dev" ]; then
    # Development mode with auto-reload
    log_info "Running in development mode"
    uvicorn backend.app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level "${LOG_LEVEL,,}" &
else
    # Production mode
    uvicorn backend.app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers "$WORKERS" \
        --log-level "${LOG_LEVEL,,}" &
fi

APP_PID=$!
log_info "Application started with PID $APP_PID"

# Wait for the application to exit
wait "$APP_PID"
EXIT_CODE=$?

log_info "Application exited with code $EXIT_CODE"
exit $EXIT_CODE
