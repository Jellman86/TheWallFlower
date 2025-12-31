# TheWallflower - Multi-stage Docker Build

# =============================================================================
# Stage 1: Build Frontend
# =============================================================================
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Copy frontend source
COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2: Python Runtime
# =============================================================================
FROM python:3.11-slim

# Build argument for target architecture (amd64, arm64)
ARG TARGETARCH

# Install system dependencies
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Download go2rtc binary for efficient video streaming
# go2rtc handles RTSP->WebRTC/MJPEG conversion with minimal CPU usage
RUN GO2RTC_VERSION="1.9.9" && \
    ARCH="${TARGETARCH:-amd64}" && \
    curl -fsSL "https://github.com/AlexxIT/go2rtc/releases/download/v${GO2RTC_VERSION}/go2rtc_linux_${ARCH}" \
        -o /usr/local/bin/go2rtc && \
    chmod +x /usr/local/bin/go2rtc && \
    echo "go2rtc v${GO2RTC_VERSION} installed for ${ARCH}"

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy frontend build from Stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy and setup entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create data directory
RUN mkdir -p /data

# Environment defaults
ENV DATABASE_URL="sqlite:////data/thewallflower.db" \
    WHISPER_HOST="whisper-live" \
    WHISPER_PORT="9090" \
    LOG_LEVEL="INFO" \
    WORKERS="1" \
    PYTHONUNBUFFERED="1" \
    PYTHONDONTWRITEBYTECODE="1" \
    PYTHONPATH="/app/backend" \
    GO2RTC_HOST="localhost" \
    GO2RTC_PORT="8954" \
    GO2RTC_RTSP_PORT="8955" \
    GO2RTC_WEBRTC_PORT="8956"

# Expose ports
# 8953: Main API
# 8954: go2rtc HTTP API & WebUI
# 8955: go2rtc RTSP server
# 8956: go2rtc WebRTC
EXPOSE 8953 8954 8955 8956

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8953/api/health || exit 1

# Run the application
ENTRYPOINT ["docker-entrypoint.sh"]
