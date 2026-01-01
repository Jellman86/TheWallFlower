/**
 * API service for TheWallflower backend.
 */

export const API_BASE = '/api';
const BASE_URL = API_BASE;

/**
 * Handle API response, throwing on error.
 */
async function handleResponse(response) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

/**
 * Stream Configuration CRUD
 */
export const streams = {
  /**
   * List all streams.
   */
  async list() {
    const response = await fetch(`${BASE_URL}/streams`);
    return handleResponse(response);
  },

  /**
   * Get a single stream by ID.
   */
  async get(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}`);
    return handleResponse(response);
  },

  /**
   * Create a new stream.
   */
  async create(data) {
    const response = await fetch(`${BASE_URL}/streams`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  /**
   * Update a stream.
   */
  async update(id, data) {
    const response = await fetch(`${BASE_URL}/streams/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  /**
   * Delete a stream.
   */
  async delete(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}`, {
      method: 'DELETE'
    });
    return handleResponse(response);
  }
};

/**
 * Stream Control
 */
export const control = {
  /**
   * Start a stream.
   */
  async start(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}/start`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Test RTSP connection without creating a stream.
   */
  async testConnection(rtspUrl) {
    const response = await fetch(`${BASE_URL}/streams/test-connection?rtsp_url=${encodeURIComponent(rtspUrl)}`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Stop a stream.
   */
  async stop(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}/stop`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Restart a stream.
   */
  async restart(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}/restart`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Force retry a stream connection (resets circuit breaker).
   */
  async forceRetry(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}/force-retry`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Get stream diagnostics including validation and worker status.
   */
  async getDiagnostics(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}/diagnostics`);
    return handleResponse(response);
  }
};

/**
 * Stream Status
 */
export const status = {
  /**
   * Get status of a specific stream.
   */
  async get(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}/status`);
    return handleResponse(response);
  },

  /**
   * Get status of all streams.
   */
  async getAll() {
    const response = await fetch(`${BASE_URL}/status`);
    return handleResponse(response);
  }
};

/**
 * Transcripts
 */
export const transcripts = {
  /**
   * Get recent transcripts for a stream.
   */
  async get(id, limit = 50) {
    const response = await fetch(`${BASE_URL}/streams/${id}/transcripts?limit=${limit}`);
    return handleResponse(response);
  }
};

/**
 * Video URLs (legacy - uses Python MJPEG streaming)
 */
export const video = {
  /**
   * Get MJPEG stream URL for a stream (legacy).
   */
  streamUrl(id) {
    return `${BASE_URL}/video/${id}`;
  },

  /**
   * Get snapshot URL for a stream.
   */
  snapshotUrl(id) {
    return `${BASE_URL}/snapshot/${id}`;
  }
};

/**
 * go2rtc streaming URLs - preferred for efficient video streaming
 *
 * All go2rtc streams are proxied through the backend API for:
 * - HTTPS/reverse proxy compatibility (no mixed content errors)
 * - No direct port access required from browser
 * - Works behind any reverse proxy configuration
 *
 * go2rtc provides:
 * - WebRTC: Low-latency (<100ms) streaming (primary method)
 * - HLS: Wide compatibility streaming
 * - Frame: Single JPEG snapshot
 */
export const go2rtc = {
  /**
   * Generate stream name from stream ID.
   */
  streamName(id) {
    return `camera_${id}`;
  },

  /**
   * Get WebRTC API URL (for custom WebRTC integration).
   * Proxied through backend API for reverse proxy compatibility.
   */
  webrtcApiUrl(id) {
    return `${BASE_URL}/streams/${id}/webrtc`;
  },

  /**
   * Get single frame (snapshot) URL.
   * Proxied through backend API for HTTPS compatibility.
   */
  frameUrl(id) {
    return `${BASE_URL}/streams/${id}/frame`;
  },

  /**
   * Get HLS streaming URL.
   * Proxied through backend API for HTTPS compatibility.
   */
  hlsUrl(id) {
    return `${BASE_URL}/streams/${id}/hls`;
  },

  /**
   * Fetch stream URLs from backend API.
   * Returns all available URLs for a stream.
   */
  async getUrls(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}/urls`);
    return handleResponse(response);
  },

  /**
   * Get go2rtc status and configured streams.
   */
  async getStatus() {
    const response = await fetch(`${BASE_URL}/go2rtc/status`);
    return handleResponse(response);
  }
};

/**
 * Audio preview and configuration
 */
export const audio = {
  /**
   * Get audio preview URL (WAV stream of processed audio).
   * Use this to hear what Whisper receives after filtering.
   */
  previewUrl(id) {
    return `${BASE_URL}/streams/${id}/audio-preview`;
  },

  /**
   * Get audio configuration for a stream.
   * Returns effective config, per-stream overrides, and global defaults.
   */
  async getConfig(id) {
    const response = await fetch(`${BASE_URL}/streams/${id}/audio-config`);
    return handleResponse(response);
  }
};

/**
 * Health check
 */
export async function healthCheck() {
  const response = await fetch(`${BASE_URL}/health`);
  return handleResponse(response);
}

/**
 * Version info
 */
export async function fetchVersion() {
  try {
    const response = await fetch(`${BASE_URL}/version`);
    if (response.ok) {
      return await response.json();
    }
  } catch {
    // Ignore errors - return fallback
  }
  return { version: "0.2.0", base_version: "0.2.0", git_hash: "unknown" };
}
