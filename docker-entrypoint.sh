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

    # Stop the Python application first
    if [ -n "$APP_PID" ]; then
        log_info "Stopping Python application (PID $APP_PID)..."
        kill -TERM "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi

    # Stop go2rtc
    if [ -n "$GO2RTC_PID" ]; then
        log_info "Stopping go2rtc (PID $GO2RTC_PID)..."
        kill -TERM "$GO2RTC_PID" 2>/dev/null || true
        wait "$GO2RTC_PID" 2>/dev/null || true
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
export DATABASE_URL="${DATABASE_URL:-sqlite:////data/thewallflower.db}"
export WHISPER_HOST="${WHISPER_HOST:-whisper-live}"
export WHISPER_PORT="${WHISPER_PORT:-9090}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"
export WORKERS="${WORKERS:-1}"

# go2rtc configuration (ports offset from Frigate defaults to avoid conflicts)
export GO2RTC_HOST="${GO2RTC_HOST:-localhost}"
export GO2RTC_PORT="${GO2RTC_PORT:-8954}"
export GO2RTC_RTSP_PORT="${GO2RTC_RTSP_PORT:-8955}"
export GO2RTC_WEBRTC_PORT="${GO2RTC_WEBRTC_PORT:-8956}"
export GO2RTC_CONFIG_PATH="${GO2RTC_CONFIG_PATH:-/data/go2rtc.yaml}"

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
log_info "  GIT_HASH: ${GIT_HASH:-unknown}"
log_info "  cd/ci is working as expected"

# Wait for WhisperLive if configured (REMOVED - Application handles reconnection)
# if [ "${WAIT_FOR_WHISPER:-false}" = "true" ]; then
#     log_info "Waiting for WhisperLive at $WHISPER_HOST:$WHISPER_PORT..."
#     ...
# fi

# Run database migrations
log_info "Initializing database schema..."

# Move to backend directory for alembic
cd /app/backend

# Check if database file exists
DB_FILE=$(echo "$DATABASE_URL" | sed 's|^sqlite:///||')

if [ -f "$DB_FILE" ]; then
    HAS_ALEMBIC=$(python3 -c "
import sqlite3
try:
    conn = sqlite3.connect('$DB_FILE')
    cursor = conn.cursor()
    cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'\")
    print('yes' if cursor.fetchone() else 'no')
    conn.close()
except Exception:
    print('no')
")
    if [ "$HAS_ALEMBIC" = "yes" ]; then
        log_info "Alembic version table found"
    else
        log_warn "No alembic_version table found; assuming fresh deployment"
    fi
else
    log_info "No database file found; migrations will create schema"
fi

# Run migrations (Safe for 'modern', 'new', and just-stamped 'legacy')
log_info "Running Alembic migrations..."
alembic upgrade head || {
    log_error "Migration failed!"
    exit 1
}

# Return to app root
cd /app

# =============================================================================
# Start go2rtc for efficient video streaming
# =============================================================================

# Create/Overwrite go2rtc config (Always overwrite to ensure validity)
log_info "Generating go2rtc configuration..."

# Build candidates list if provided
CANDIDATES_YAML=""

# Option 1: Full list provided manually
if [ -n "$WEBRTC_CANDIDATES" ]; then
    log_info "Adding WebRTC candidates from list: $WEBRTC_CANDIDATES"
    CANDIDATES_YAML="    - \"$WEBRTC_CANDIDATES\""

# Option 2: Constructed from IP/Port components (Easier for users)
elif [ -n "$WEBRTC_ADVERTISED_IP" ]; then
    # Default to standard port if not set
    CAND_PORT="${WEBRTC_ADVERTISED_PORT:-$GO2RTC_WEBRTC_PORT}"
    log_info "Adding WebRTC candidate from IP/Port: $WEBRTC_ADVERTISED_IP:$CAND_PORT"
    CANDIDATES_YAML="    - \"$WEBRTC_ADVERTISED_IP:$CAND_PORT\""
fi

cat > "$GO2RTC_CONFIG_PATH" << EOYAML
# go2rtc configuration for TheWallflower
api:
  listen: ":${GO2RTC_PORT}"
  origin: "*"

ffmpeg:
  bin: "ffmpeg"

rtsp:
  listen: ":${GO2RTC_RTSP_PORT}"

webrtc:
  listen: ":${GO2RTC_WEBRTC_PORT}"
  ice_servers:
    - urls: [ "stun:stun.l.google.com:19302" ]
  candidates:
$CANDIDATES_YAML

log:
  level: debug
EOYAML

# Start go2rtc in background
log_info "Starting go2rtc..."
/usr/local/bin/go2rtc -config "$GO2RTC_CONFIG_PATH" &
GO2RTC_PID=$!
log_info "go2rtc started with PID $GO2RTC_PID"

# Wait for go2rtc to be ready
wait_for_go2rtc() {
    local max_attempts=30
    local attempt=1
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://localhost:${GO2RTC_PORT}/api/streams" > /dev/null 2>&1; then
            return 0
        fi
        log_info "Waiting for go2rtc... (attempt $attempt/$max_attempts)"
        sleep 1
        attempt=$((attempt + 1))
    done
    return 1
}

if wait_for_go2rtc; then
    log_info "go2rtc is ready on ports: API=$GO2RTC_PORT, RTSP=$GO2RTC_RTSP_PORT, WebRTC=$GO2RTC_WEBRTC_PORT"
else
    log_warn "go2rtc may not be fully ready, but continuing anyway"
fi

# =============================================================================
# Start the application
# =============================================================================
log_info "Starting TheWallflower..."

if [ "$1" = "dev" ]; then
    # Development mode with auto-reload
    log_info "Running in development mode"
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8953 \
        --reload \
        --log-level "${LOG_LEVEL,,}" &
else
    # Production mode
    uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8953 \
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
