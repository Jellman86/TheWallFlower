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
 * Video URLs (not fetch, direct URL for img/video src)
 */
export const video = {
  /**
   * Get MJPEG stream URL for a stream.
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
 * Health check
 */
export async function healthCheck() {
  const response = await fetch(`${BASE_URL}/health`);
  return handleResponse(response);
}
