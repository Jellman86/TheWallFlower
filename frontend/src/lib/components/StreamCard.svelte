<script>
  import { status, transcripts, control, go2rtc, API_BASE } from '../services/api.js';
  import Icon from './Icons.svelte';

  let {
    stream,
    onEdit = () => {},
    onFocus = () => {},
    focused = false
  } = $props();

  let streamStatus = $state(null);
  let transcriptList = $state([]);
  let isLoading = $state(false);
  let showTranscripts = $state(true);
  let eventSource = $state(null);
  let reconnectTimeout = $state(null);

  // Image error handling - use a stable cache buster that only changes on manual retry
  let imageError = $state(false);
  let imageRetryCount = $state(0);
  let imageRetryTimeout = $state(null);
  let imageCacheBuster = $state(Date.now()); // Only changes on explicit retry
  let isForceRetrying = $state(false);
  let sseError = $state(null);

  // Max retries before giving up on image
  const MAX_IMAGE_RETRIES = 5;

  // Derived state
  let isRunning = $derived(streamStatus?.is_running ?? false);
  let isConnected = $derived(streamStatus?.video_connected ?? false);
  let hasWhisper = $derived(stream.whisper_enabled && streamStatus?.whisper_connected);

  // Enhanced connection state
  let connectionState = $derived(streamStatus?.connection_state ?? 'stopped');
  let retryCount = $derived(streamStatus?.retry_count ?? 0);
  let circuitBreakerOpen = $derived(streamStatus?.circuit_breaker_state === 'open');

  // Computed display state
  let displayState = $derived.by(() => {
    if (!isRunning) return 'stopped';
    if (circuitBreakerOpen) return 'failed';
    if (connectionState === 'connected' && isConnected) return 'connected';
    if (connectionState === 'retrying') return 'retrying';
    return 'connecting';
  });

  // Whether to show the image (connected and not too many errors)
  let showImage = $derived(isConnected && !imageError && imageRetryCount < MAX_IMAGE_RETRIES);

  // Connect to SSE for real-time updates
  $effect(() => {
    const currentStreamId = stream?.id;
    if (!currentStreamId) return;

    // Initial fetch for immediate data
    fetchStatus();
    if (stream.whisper_enabled) {
      fetchTranscripts();
    }

    // Connect to SSE
    connectSSE();

    // Cleanup function
    return () => {
      cleanupAll();
    };
  });

  function cleanupAll() {
    // Clear all timeouts
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    if (imageRetryTimeout) {
      clearTimeout(imageRetryTimeout);
      imageRetryTimeout = null;
    }
    // Close SSE
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  function connectSSE() {
    // Close existing connection first
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    const url = `${API_BASE}/streams/${stream.id}/events`;
    eventSource = new EventSource(url);

    eventSource.addEventListener('status', (event) => {
      try {
        const data = JSON.parse(event.data);
        streamStatus = data.data;
        // Reset image error state when status shows connected
        if (data.data?.video_connected && imageError) {
          imageError = false;
          imageRetryCount = 0;
          imageCacheBuster = Date.now(); // Force reload with new cache buster
        }
      } catch (e) {
        console.error('Failed to parse status event:', e);
      }
    });

    eventSource.addEventListener('transcript', (event) => {
      try {
        const data = JSON.parse(event.data);
        const transcript = data.data;
        // Add to front of list (newest first)
        transcriptList = [transcript, ...transcriptList.slice(0, 9)];
      } catch (e) {
        console.error('Failed to parse transcript event:', e);
      }
    });

    eventSource.addEventListener('error', (event) => {
      try {
        const data = JSON.parse(event.data);
        sseError = data.data?.error || 'Stream error occurred';
        console.error('Stream error:', data.data?.error);
      } catch (e) {
        // Connection error, not a data error - ignore parse errors
      }
    });

    eventSource.onerror = () => {
      sseError = 'Connection to server lost';
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }

      // Reconnect after 5 seconds - but only if we haven't been cleaned up
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      reconnectTimeout = setTimeout(() => {
        if (stream?.id) {
          sseError = null;
          connectSSE();
        }
      }, 5000);
    };
  }

  function handleImageError() {
    // Only handle error if we haven't exceeded max retries
    if (imageRetryCount >= MAX_IMAGE_RETRIES) {
      imageError = true;
      return;
    }

    imageError = true;
    imageRetryCount++;

    // Exponential backoff for image retries (2s, 4s, 8s, 16s, 32s)
    const delay = Math.min(2000 * Math.pow(2, imageRetryCount - 1), 32000);

    if (imageRetryTimeout) clearTimeout(imageRetryTimeout);
    imageRetryTimeout = setTimeout(() => {
      if (imageRetryCount < MAX_IMAGE_RETRIES) {
        imageError = false;
        imageCacheBuster = Date.now(); // Update cache buster for retry
      }
    }, delay);
  }

  function handleImageLoad() {
    imageError = false;
    imageRetryCount = 0;
  }

  function handleManualImageRetry() {
    imageError = false;
    imageRetryCount = 0;
    imageCacheBuster = Date.now();
  }

  async function handleForceRetry() {
    isForceRetrying = true;
    try {
      await control.forceRetry(stream.id);
      // Reset image state
      handleManualImageRetry();
    } catch (e) {
      console.error('Failed to force retry:', e);
    }
    isForceRetrying = false;
  }

  function disconnectSSE() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  async function fetchStatus() {
    try {
      streamStatus = await status.get(stream.id);
    } catch (e) {
      console.error('Failed to fetch status:', e);
    }
  }

  async function fetchTranscripts() {
    try {
      const result = await transcripts.get(stream.id, 10);
      transcriptList = result.transcripts || [];
    } catch (e) {
      // Stream might not be running
    }
  }

  async function handleStart() {
    isLoading = true;
    try {
      await control.start(stream.id);
      // Reset image state for fresh start
      handleManualImageRetry();
      await fetchStatus();
    } catch (e) {
      console.error('Failed to start stream:', e);
    }
    isLoading = false;
  }

  async function handleStop() {
    isLoading = true;
    try {
      await control.stop(stream.id);
      await fetchStatus();
    } catch (e) {
      console.error('Failed to stop stream:', e);
    }
    isLoading = false;
  }

  async function handleRestart() {
    isLoading = true;
    try {
      await control.restart(stream.id);
      // Reset image state for fresh start
      handleManualImageRetry();
      await fetchStatus();
    } catch (e) {
      console.error('Failed to restart stream:', e);
    }
    isLoading = false;
  }
</script>

<div class="bg-[var(--color-bg-card)] rounded-lg overflow-hidden shadow-lg border border-[var(--color-border)] {focused ? 'col-span-2 row-span-2' : ''}">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-2 bg-[var(--color-bg-hover)]">
    <div class="flex items-center gap-2">
      <span class="status-dot {displayState === 'connected' ? 'connected' : displayState === 'retrying' || displayState === 'connecting' ? 'connecting' : 'disconnected'}"></span>
      <h3 class="font-medium text-sm truncate">{stream.name}</h3>
      {#if streamStatus?.error}
        <span class="text-xs text-[var(--color-danger)]" title={streamStatus.error}>!</span>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      <!-- Status indicators -->
      <div class="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
        {#if displayState === 'retrying'}
          <span class="px-1.5 py-0.5 bg-[var(--color-warning)]/20 text-[var(--color-warning)] rounded animate-pulse">
            Retry #{retryCount}
          </span>
        {:else if displayState === 'failed'}
          <span class="px-1.5 py-0.5 bg-[var(--color-danger)]/20 text-[var(--color-danger)] rounded">
            Failed
          </span>
        {:else if streamStatus?.fps}
          <span class="px-1.5 py-0.5 bg-[var(--color-bg-dark)] rounded">{Math.round(streamStatus.fps)} fps</span>
        {/if}
        {#if isRunning && streamStatus?.ffmpeg_restarts > 1}
          <span class="px-1.5 py-0.5 bg-[var(--color-warning)]/20 text-[var(--color-warning)] rounded" title="FFmpeg restarts">
            R:{streamStatus.ffmpeg_restarts}
          </span>
        {/if}
      </div>
      <button
        onclick={() => onFocus(stream)}
        class="p-1 hover:bg-[var(--color-bg-dark)] rounded transition-colors"
        title="Focus view"
      >
        <Icon name="maximize" size={16} />
      </button>
      <button
        onclick={() => onEdit(stream)}
        class="p-1 hover:bg-[var(--color-bg-dark)] rounded transition-colors"
        title="Settings"
      >
        <Icon name="settings" size={16} />
      </button>
    </div>
  </div>

  <!-- Video with error handling -->
  <div class="relative">
    {#if showImage}
      <!-- go2rtc MJPEG streaming - efficient, low CPU -->
      <img
        src="{go2rtc.mjpegUrl(stream.id)}?t={imageCacheBuster}"
        alt={stream.name}
        class="stream-video"
        onerror={handleImageError}
        onload={handleImageLoad}
      />
    {:else}
      <div class="stream-video flex items-center justify-center bg-black">
        <div class="text-center p-4">
          {#if displayState === 'connected' && (imageError || imageRetryCount >= MAX_IMAGE_RETRIES)}
            <Icon name="alert-triangle" size={24} class="mx-auto mb-2 text-[var(--color-warning)]" />
            <div class="text-[var(--color-warning)] text-sm">Stream error</div>
            {#if imageRetryCount >= MAX_IMAGE_RETRIES}
              <div class="text-[var(--color-text-muted)] text-xs mt-1">Max retries reached</div>
              <button
                onclick={handleManualImageRetry}
                class="mt-2 px-3 py-1 text-xs bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] rounded transition-colors"
              >
                Retry
              </button>
            {:else}
              <div class="text-[var(--color-text-muted)] text-xs mt-1">Retrying... ({imageRetryCount}/{MAX_IMAGE_RETRIES})</div>
            {/if}
          {:else if displayState === 'connecting'}
            <div class="animate-pulse text-[var(--color-warning)]">Connecting...</div>
          {:else if displayState === 'retrying'}
            <Icon name="rotate" size={24} class="mx-auto mb-2 text-[var(--color-warning)] animate-spin" />
            <div class="text-[var(--color-warning)] text-sm">Reconnecting</div>
            <div class="text-[var(--color-text-muted)] text-xs mt-1">Attempt {retryCount}</div>
          {:else if displayState === 'failed'}
            <Icon name="x" size={32} class="mx-auto mb-2 text-[var(--color-danger)]" />
            <div class="text-[var(--color-danger)] text-sm font-medium">Connection Failed</div>
            <div class="text-[var(--color-text-muted)] text-xs mt-1 max-w-48">
              {streamStatus?.error || 'Unable to connect after multiple attempts'}
            </div>
            <button
              onclick={handleForceRetry}
              disabled={isForceRetrying}
              class="mt-3 px-3 py-1.5 text-xs bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] rounded transition-colors disabled:opacity-50"
            >
              {#if isForceRetrying}
                <Icon name="rotate" size={14} class="inline animate-spin mr-1" />
              {/if}
              Retry Now
            </button>
          {:else if streamStatus?.error}
            <div class="text-[var(--color-danger)] text-sm">{streamStatus.error}</div>
          {:else}
            <div class="text-[var(--color-text-muted)]">Stream stopped</div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- SSE Error Banner -->
    {#if sseError}
      <div class="absolute bottom-0 left-0 right-0 bg-[var(--color-danger)]/90 text-white text-xs px-2 py-1">
        {sseError}
      </div>
    {/if}

    <!-- Whisper indicator -->
    {#if stream.whisper_enabled}
      <div class="absolute top-2 right-2">
        {#if hasWhisper}
          <Icon name="volume" size={18} class="text-[var(--color-success)]" />
        {:else}
          <Icon name="volume-x" size={18} class="text-[var(--color-text-muted)]" />
        {/if}
      </div>
    {/if}
  </div>

  <!-- Transcript area (if enabled) -->
  {#if stream.whisper_enabled && showTranscripts}
    <div class="transcript-box {focused ? 'h-48' : 'h-24'} overflow-y-auto p-2 bg-black/30 border-t border-[var(--color-border)]">
      {#if transcriptList.length > 0}
        <div class="space-y-1">
          {#each transcriptList as transcript}
            <div class="flex gap-2 text-xs">
              <span class="text-[var(--color-text-muted)] font-mono flex-shrink-0">
                {#if transcript.created_at}
                  {new Date(transcript.created_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'})}
                {:else if transcript.start_time !== undefined}
                  {Math.floor(transcript.start_time / 60).toString().padStart(2, '0')}:{Math.floor(transcript.start_time % 60).toString().padStart(2, '0')}
                {/if}
              </span>
              <span class="{transcript.is_final ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)] italic'}">
                {transcript.text}
              </span>
            </div>
          {/each}
        </div>
      {:else}
        <p class="text-xs text-[var(--color-text-muted)] italic">Waiting for speech...</p>
      {/if}
    </div>
  {/if}

  <!-- Controls -->
  <div class="flex items-center justify-between px-4 py-2 border-t border-[var(--color-border)]">
    <div class="flex gap-2">
      {#if !isRunning}
        <button
          onclick={handleStart}
          disabled={isLoading}
          class="flex items-center gap-1 px-3 py-1 text-xs bg-[var(--color-success)] hover:opacity-80 rounded transition-opacity disabled:opacity-50"
        >
          <Icon name="play" size={14} />
          Start
        </button>
      {:else}
        <button
          onclick={handleStop}
          disabled={isLoading}
          class="flex items-center gap-1 px-3 py-1 text-xs bg-[var(--color-danger)] hover:opacity-80 rounded transition-opacity disabled:opacity-50"
        >
          <Icon name="stop" size={14} />
          Stop
        </button>
        <button
          onclick={handleRestart}
          disabled={isLoading}
          class="flex items-center gap-1 px-3 py-1 text-xs bg-[var(--color-warning)] hover:opacity-80 rounded transition-opacity disabled:opacity-50"
        >
          <Icon name="rotate" size={14} />
          Restart
        </button>
      {/if}
    </div>
    {#if stream.whisper_enabled}
      <button
        onclick={() => showTranscripts = !showTranscripts}
        class="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
      >
        {showTranscripts ? 'Hide' : 'Show'} transcripts
      </button>
    {/if}
  </div>
</div>
