# TheWallflower

A self-hosted, privacy-focused AI companion for Frigate NVR with real-time Speech-to-Text and high-accuracy Face Recognition.

> ⚠️ **Warning:** This project is under active, experimental development. Features change often, and the main branch is frequently broken. We prioritize moving fast and testing new AI integrations over stability at this stage. Use at your own risk.

## Current Status: v0.3.0

TheWallflower now pairs with Frigate for DVR features, while the Python backend focuses on AI processing (Whisper + InsightFace).

## Features

- **Low-Latency WebRTC** - Primary viewing via WebRTC for <100ms latency.
- **Frigate DVR Integration** - Camera definitions and recordings handled by Frigate.
- **Advanced Face Recognition** - Robust identity management using multi-embedding averages and local pretraining (`/data/faces/known/{name}/`).
- **Real-time Speech-to-Text** - Transcription of RTSP audio streams powered by WhisperLive with aggressive anti-hallucination filtering.
- **Audio Pre-filtering** - RMS Energy gating and Silero VAD (Voice Activity Detection) ensure Whisper only processes actual speech.
- **Event Snapshots** - High-definition full-frame captures for every face detection event.
- **Frigate-Synced Cameras** - Camera list is sourced from Frigate config.

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Svelte 5 (Runes) + TailwindCSS v4 |
| Backend | FastAPI + SQLModel + Alembic |
| Video Engine | go2rtc (Embedded) |
| Speech AI | WhisperLive + Faster-Whisper + Silero VAD |
| Vision AI | InsightFace (buffalo_l) + ONNX Runtime |
| Database | SQLite (WAL Mode) |
| Container | Docker (Multi-stage build) |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Intel GPU (recommended for OpenVINO) or NVIDIA GPU

### Running with Docker Compose

```bash
# Clone the repository
git clone https://github.com/Jellman86/TheWallFlower.git
cd TheWallflower

# Copy and customize environment (essential for WebRTC)
cp .env.example .env
# Edit .env and set WEBRTC_ADVERTISED_IP to your server's local IP
# Set FRIGATE_URL to your Frigate base URL (e.g., http://frigate:5000)

# Start the services
docker compose up -d
```

The web UI will be available at `http://localhost:8953`

### GPU Acceleration

TheWallflower supports hardware acceleration for AI tasks:
- **Intel iGPU:** Set `WHISPER_IMAGE` to the `openvino` variant in `.env`.
- **NVIDIA GPU:** Set `WHISPER_IMAGE` to the `gpu` variant and uncomment the `deploy` section in `docker-compose.yml`.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TheWallflower Container                          │
│                                                                          │
│  ┌────────────────┐      ┌─────────────────┐      ┌─────────────────┐  │
│  │    FastAPI     │◄────►│     go2rtc      │◄────►│   RTSP Camera   │  │
│  │    Backend     │      │  (Video Engine) │      │                 │  │
│  │    :8953       │      │  :8954/8955/8956│      │                 │  │
└───────┬────────┘      └─────────────────┘      └─────────────────┘  │
        │                                                              │
        │ Audio Worker Pipeline:                                       │
        │  FFmpeg ──► Bandpass ──► Energy Gate ──► Silero VAD          │
        │                                                              │
        ▼                                                              │
┌────────────────┐                                                    │
│  WhisperLive   │ ◄── Only verified speech chunks reach here        │
│   (External)   │                                                    │
│    :9090       │                                                    │
└────────────────┘                                                    │
                                                                       │
        │ Face Worker Pipeline:                                        │
        │  Fetch Frame ──► InsightFace ──► Identify ──► DB Event       │
        │                                                              │
        │ Frigate (External DVR):                                      │
        │  Recordings + timeline + detections                          │
        │                                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Face Recognition Pretraining

To skip the "Unknown" phase, you can pretrain the system with existing photos:
1. Create a folder: `/data/faces/known/John_Smith/`
2. Drop `.jpg` or `.png` photos of John into that folder.
3. Restart the container.
4. TheWallflower will automatically detect faces, generate embeddings, and register the identity.

## Project Structure

```
TheWallflower/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI application & SSE
│   │   ├── stream_manager.py # Worker lifecycle
│   │   ├── worker.py         # Audio extraction & VAD
│   │   ├── workers/          # Background tasks (Face)
│   │   └── services/         # Business logic (Detection)
│   └── migrations/           # Alembic DB migrations
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/   # WebRTCPlayer, FaceCard
│   │   │   └── services/     # API client (api.js)
│   └── public/
├── docker-compose.yml
├── Dockerfile
└── docker-entrypoint.sh
```

## License

MIT License - see [LICENSE](LICENSE) for details.
