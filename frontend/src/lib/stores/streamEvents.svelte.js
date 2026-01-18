import { API_BASE } from '../services/api.js';

/**
 * Global store for stream events (SSE).
 * Manages a single connection to /api/events and dispatches updates to components.
 */
function createStreamStore() {
  // Reactive state using Svelte 5 runes
  let connectionStatus = $state('disconnected');
  let streamStatuses = $state({}); // stream_id -> status object
  let streamTranscripts = $state({}); // stream_id -> Array<transcript>
  
  let eventSource = null;
  let reconnectTimeout = null;

  function connect() {
    if (eventSource) return;

    const url = `${API_BASE}/events`;
    // Add timestamp to prevent caching
    eventSource = new EventSource(`${url}?t=${Date.now()}`);
    connectionStatus = 'connecting';

    eventSource.onopen = () => {
      connectionStatus = 'connected';
      console.log('Global SSE connected');
    };

    eventSource.addEventListener('status', (event) => {
      try {
        const payload = JSON.parse(event.data);
        const { stream_id, data } = payload;
        if (stream_id) {
          // Replace object to ensure Object.values() reactivity in derivations
          streamStatuses = { ...streamStatuses, [stream_id]: data };
        }
      } catch (e) {
        console.error('Failed to parse status event:', e);
      }
    });

    eventSource.addEventListener('transcript', (event) => {
      try {
        const payload = JSON.parse(event.data);
        const { stream_id, data: transcript } = payload;
        
        if (stream_id) {
          const currentTranscripts = streamTranscripts[stream_id] || [];
          
          // Find if we already have this segment by ID (preferred) or start time
          const existingIndex = currentTranscripts.findIndex(t => 
            (transcript.id && t.id === transcript.id) || 
            Math.abs(t.start_time - transcript.start_time) < 0.1
          );

          let updatedTranscripts;
          if (existingIndex !== -1) {
            // Update existing segment
            updatedTranscripts = [...currentTranscripts];
            updatedTranscripts[existingIndex] = { ...updatedTranscripts[existingIndex], ...transcript };
          } else {
            // New segment, add to front and enforce limit
            updatedTranscripts = [transcript, ...currentTranscripts].slice(0, 50);
          }
          
          // Replace object to trigger reactivity
          streamTranscripts = { ...streamTranscripts, [stream_id]: updatedTranscripts };
        }
      } catch (e) {
        console.error('Failed to parse transcript event:', e);
      }
    });

    eventSource.onerror = (err) => {
      console.error('Global SSE error:', err);
      connectionStatus = 'error';
      disconnect();
      
      // Attempt reconnect after 5 seconds
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      reconnectTimeout = setTimeout(() => {
        connect();
      }, 5000);
    };
  }

  function disconnect() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    connectionStatus = 'disconnected';
  }
  
  // Method to clear transcripts for a stream (e.g. on restart)
  function clearTranscripts(streamId) {
    if (streamTranscripts[streamId]) {
      streamTranscripts = { ...streamTranscripts, [streamId]: [] };
    }
  }

  return {
    get connectionStatus() { return connectionStatus; },
    get allStatuses() { return streamStatuses; },
    getStreamStatus: (id) => streamStatuses[id],
    getTranscripts: (id) => streamTranscripts[id] || [],
    connect,
    disconnect,
    clearTranscripts
  };
}

export const streamEvents = createStreamStore();
