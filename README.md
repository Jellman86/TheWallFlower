# TheWallflower

A self-hosted, containerized NVR (Network Video Recorder) that performs real-time Speech-to-Text on RTSP streams.

## Features

- **UI-First Configuration** - No YAML files needed. Add and manage cameras through the web interface.
- **Real-time Speech-to-Text** - Powered by WhisperLive for live transcription of audio streams.
- **MJPEG Video Streaming** - Low-latency video display in browser.
- **Modular Architecture** - Extensible pipeline for future features (face detection, etc.)
- **Graceful Shutdown** - Proper signal handling for clean container stops.
- **Health Monitoring** - Built-in health checks for container orchestration.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Svelte 5 + TailwindCSS v4 (Vite) |
| Backend | Python 3.11 + FastAPI + SQLModel |
| Database | SQLite |
| AI Engine | WhisperLive (external WebSocket) |
| Container | Docker + Docker Compose |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- NVIDIA GPU (optional, for faster Whisper inference)

### Running with Docker Compose

```bash
# Clone the repository
git clone https://github.com/yourusername/TheWallflower.git
cd TheWallflower

# Copy and customize environment (optional)
cp .env.example .env

# Start the services
docker compose up -d

# View logs
docker compose logs -f
```

The web UI will be available at `http://localhost:8080`

### GPU Support (NVIDIA)

For GPU-accelerated Whisper inference, uncomment the GPU section in `docker-compose.yml`:

```yaml
whisper-live:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Development Setup

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Start the backend (dev mode)
uvicorn app.main:app --reload --port 8953
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        TheWallflower                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Frontend   │    │   Backend    │    │ WhisperLive  │      │
│  │  (Svelte 5)  │◄──►│  (FastAPI)   │◄──►│   (GPU/CPU)  │      │
│  └──────────────┘    └──────┬───────┘    └──────────────┘      │
│                             │                                    │
│                      ┌──────▼───────┐                           │
│                      │   SQLite     │                           │
│                      │  (streams.db)│                           │
│                      └──────────────┘                           │
├─────────────────────────────────────────────────────────────────┤
│                        RTSP Cameras                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                         │
│  │ Camera1 │  │ Camera2 │  │ Camera3 │  ...                    │
│  └─────────┘  └─────────┘  └─────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Stream Configuration

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/streams` | List all stream configurations |
| POST | `/api/streams` | Create a new stream |
| GET | `/api/streams/{id}` | Get a specific stream |
| PATCH | `/api/streams/{id}` | Update a stream |
| DELETE | `/api/streams/{id}` | Delete a stream |

### Stream Control

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/streams/{id}/start` | Start a stream worker |
| POST | `/api/streams/{id}/stop` | Stop a stream worker |
| POST | `/api/streams/{id}/restart` | Restart a stream worker |

### Stream Status & Monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/streams/{id}/status` | Get status of a specific stream |
| GET | `/api/status` | Get status of all streams |
| GET | `/api/streams/{id}/transcripts` | Get recent transcripts |
| GET | `/api/health` | Health check |

### Video Streaming

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/video/{id}` | MJPEG video stream |
| GET | `/api/snapshot/{id}` | Single JPEG snapshot |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8080` | External port for web UI |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `WORKERS` | `1` | Number of uvicorn workers |
| `WHISPER_MODEL` | `base.en` | Whisper model to use |
| `DATABASE_URL` | `sqlite:///data/thewallflower.db` | Database connection string |
| `JPEG_QUALITY` | `80` | MJPEG stream quality (1-100) |

See `.env.example` for all available options.

## Configuration

Streams are configured via the web UI. Each stream has:

| Field | Type | Description |
|-------|------|-------------|
| name | string | Display name for the stream |
| rtsp_url | string | RTSP URL of the camera |
| whisper_enabled | boolean | Enable speech-to-text |
| face_detection_enabled | boolean | Enable face detection (future) |

## Project Structure

```
TheWallflower/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI application
│   │   ├── config.py         # Environment configuration
│   │   ├── db.py             # Database setup
│   │   ├── models.py         # SQLModel schemas
│   │   ├── processors.py     # Frame processors (MJPEG, snapshots)
│   │   ├── stream_manager.py # Worker lifecycle management
│   │   └── worker.py         # Stream worker (video/audio)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.svelte        # Main dashboard
│   │   └── lib/
│   │       ├── components/   # StreamCard, SettingsModal
│   │       └── services/     # API client
│   └── package.json
├── docker-compose.yml
├── Dockerfile
├── docker-entrypoint.sh
└── .env.example
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
