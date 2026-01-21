/**
 * API service for TheWallflower backend.
 */

export const API_BASE = '/api';
const BASE_URL = API_BASE;

/** Default request timeout in milliseconds */
const DEFAULT_TIMEOUT = 30000;

/**
 * Fetch with timeout support.
 * @param {string} url - URL to fetch
 * @param {RequestInit} options - Fetch options
 * @param {number} timeout - Timeout in ms (default 30s)
 */
async function fetchWithTimeout(url, options = {}, timeout = DEFAULT_TIMEOUT) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

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
 * Stream Configuration
 */
export const streams = {
  /**
   * List all streams.
   */
  async list() {
    const response = await fetchWithTimeout(`${BASE_URL}/streams`);
    return handleResponse(response);
  },

  /**
   * Get a single stream by ID.
   */
  async get(id) {
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}`);
    return handleResponse(response);
  },

  /**
   * Update a stream.
   */
  async update(id, data) {
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    return handleResponse(response);
  },

  /**
   * Refresh streams from Frigate.
   */
  async refresh() {
    const response = await fetchWithTimeout(`${BASE_URL}/streams/refresh`, {
      method: 'POST'
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
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/start`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Stop a stream.
   */
  async stop(id) {
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/stop`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Restart a stream.
   */
  async restart(id) {
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/restart`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Force retry a stream connection (resets circuit breaker).
   */
  async forceRetry(id) {
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/force-retry`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Get stream diagnostics including validation and worker status.
   */
  async getDiagnostics(id) {
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/diagnostics`);
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
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/status`);
    return handleResponse(response);
  },

  /**
   * Get status of all streams.
   */
  async getAll() {
    const response = await fetchWithTimeout(`${BASE_URL}/status`);
    return handleResponse(response);
  }
};

/**
 * Frigate
 */
export const frigate = {
  /**
   * Get Frigate connection info.
   */
  async getInfo() {
    const response = await fetchWithTimeout(`${BASE_URL}/frigate`);
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
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/transcripts?limit=${limit}`);
    return handleResponse(response);
  }
};

/**
 * Faces
 */
export const faces = {
  /**
   * List faces.
   * @returns {Promise<{items: Array, total: number, limit: number, offset: number, has_more: boolean}>}
   */
  async list(known = null, limit = 50, offset = 0) {
    let query = `?limit=${limit}&offset=${offset}`;
    if (known !== null) {
      query += `&known=${known}`;
    }
    const response = await fetchWithTimeout(`${BASE_URL}/faces${query}`);
    return handleResponse(response);
  },

  /**
   * List face events.
   * @returns {Promise<{items: Array, total: number, limit: number, offset: number, has_more: boolean}>}
   */
  async listEvents(faceId = null, streamId = null, limit = 50, offset = 0) {
    let query = `?limit=${limit}&offset=${offset}`;
    if (faceId !== null) query += `&face_id=${faceId}`;
    if (streamId !== null) query += `&stream_id=${streamId}`;

    const response = await fetchWithTimeout(`${BASE_URL}/faces/events/all${query}`);
    return handleResponse(response);
  },

  /**
   * List embeddings for a face.
   */
  async listEmbeddings(id) {
    const response = await fetchWithTimeout(`${BASE_URL}/faces/${id}/embeddings`);
    return handleResponse(response);
  },

  /**
   * Update a face.
   */
  async update(id, name, isKnown) {
    let query = [];
    if (name !== undefined) query.push(`name=${encodeURIComponent(name)}`);
    if (isKnown !== undefined) query.push(`is_known=${isKnown}`);

    const response = await fetchWithTimeout(`${BASE_URL}/faces/${id}?${query.join('&')}`, {
      method: 'PATCH'
    });
    return handleResponse(response);
  },

  /**
   * Delete a face.
   */
  async delete(id) {
    const response = await fetchWithTimeout(`${BASE_URL}/faces/${id}`, {
      method: 'DELETE'
    });
    return handleResponse(response);
  },

  /**
   * Get known face names for autocomplete.
   * @returns {Promise<Array<{name: string, face_id: number, embedding_count: number, thumbnail_path: string}>>}
   */
  async getKnownNames() {
    const response = await fetchWithTimeout(`${BASE_URL}/faces/names`);
    return handleResponse(response);
  },

  /**
   * Get faces grouped by name.
   * @returns {Promise<{groups: Array, total_groups: number, total_faces: number}>}
   */
  async getGrouped(knownOnly = false) {
    const response = await fetchWithTimeout(`${BASE_URL}/faces/grouped?known_only=${knownOnly}`);
    return handleResponse(response);
  },

  /**
   * Merge multiple faces into one identity.
   * @param {number[]} faceIds - IDs of faces to merge
   * @param {string} targetName - Name for the merged identity
   * @param {number|null} keepFaceId - Optional ID of face to keep as primary
   * @returns {Promise<{merged_face_id: number, merged_count: number, total_embeddings: number, name: string}>}
   */
  async merge(faceIds, targetName, keepFaceId = null) {
    const body = {
      face_ids: faceIds,
      target_name: targetName
    };
    if (keepFaceId !== null) {
      body.keep_face_id = keepFaceId;
    }
    const response = await fetchWithTimeout(`${BASE_URL}/faces/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return handleResponse(response);
  },

  /**
   * Assign a face to an existing person (merges if name exists).
   * @param {number} faceId - ID of face to assign
   * @param {string} targetName - Name to assign to (merges if exists)
   * @returns {Promise<{merged_face_id: number, merged_count: number, total_embeddings: number, name: string}>}
   */
  async assignToExisting(faceId, targetName) {
    const response = await fetchWithTimeout(`${BASE_URL}/faces/${faceId}/assign/${encodeURIComponent(targetName)}`, {
      method: 'POST'
    });
    return handleResponse(response);
  },

  /**
   * Get snapshot URL.
   */
  snapshotUrl(filename) {
    if (!filename) return null;
    // filename might be a full path from DB, we just need the basename
    const parts = filename.split('/');
    const name = parts[parts.length - 1];
    return `${API_BASE}/snapshots/${name}`;
  },

  /**
   * Get embedding crop URL.
   */
  embeddingUrl(filename) {
    if (!filename) return null;
    const parts = filename.split('/');
    const name = parts[parts.length - 1];
    return `${API_BASE}/embeddings/${name}`;
  },

  /**
   * Get thumbnail URL.
   */
  thumbnailUrl(id) {
    // Add timestamp to bust cache if needed
    return `${API_BASE}/faces/thumbnails/${id}.jpg`;
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
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/urls`);
    return handleResponse(response);
  },

  /**
   * Get go2rtc status and configured streams.
   */
  async getStatus() {
    const response = await fetchWithTimeout(`${BASE_URL}/go2rtc/status`);
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
    const response = await fetchWithTimeout(`${BASE_URL}/streams/${id}/audio-config`);
    return handleResponse(response);
  }
};

/**
 * Health check
 */
export async function healthCheck() {
  const response = await fetchWithTimeout(`${BASE_URL}/health`, {}, 10000);
  return handleResponse(response);
}

/**
 * Version info
 */
export async function fetchVersion() {
  try {
    const response = await fetchWithTimeout(`${BASE_URL}/version`, {}, 5000);
    if (response.ok) {
      return await response.json();
    }
  } catch {
    // Ignore errors - return fallback
  }
  return { version: "0.3.0", base_version: "0.3.0", git_hash: "unknown" };
}
