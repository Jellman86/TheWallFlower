<script>
  import { status, transcripts, control, go2rtc, API_BASE } from '../services/api.js';
  import { streamEvents } from '../stores/streamEvents.svelte.js';
  import Icon from './Icons.svelte';
  import WebRTCPlayer from './WebRTCPlayer.svelte';

  let {
    stream,
    onEdit = () => {},
    onFocus = () => {},
    focused = false
  } = $props();

  // Use global store for status and transcripts
  let streamStatus = $derived(stream && stream.id ? streamEvents.getStreamStatus(stream.id) : null);
  let transcriptList = $derived(stream && stream.id ? streamEvents.getTranscripts(stream.id) : []);

  let isLoading = $state(false);
  let showTranscripts = $state(true);
  
  // Streaming mode: 'webrtc' or 'mjpeg'
  // TODO: Move this to global settings or per-stream config
  let streamMode = $state('webrtc'); 

  // Image error handling (Legacy MJPEG)
  let imageError = $state(false);
  let imageRetryCount = $state(0);
  let imageRetryTimeout = $state(null);
  let imageCacheBuster = $state(Date.now()); 
  let isForceRetrying = $state(false);

  // WebRTC State
  let webrtcStatus = $state('connecting'); // connecting, connected, error

  const MAX_IMAGE_RETRIES = 5;

  // Derived state
  let isRunning = $derived(streamStatus?.is_running ?? false);
  let isConnected = $derived(streamStatus?.video_connected ?? false);
  let hasWhisper = $derived(stream.whisper_enabled && streamStatus?.whisper_connected);

  // Enhanced connection state
  let connectionState = $derived(streamStatus?.connection_state ?? 'stopped');
  let retryCount = $derived(streamStatus?.retry_count ?? 0);
  let circuitBreakerOpen = $derived(streamStatus?.circuit_breaker_state === 'open');

  // Computed display state (Logic unified for both modes)
  let displayState = $derived.by(() => {
    if (!isRunning) return 'stopped';
    if (circuitBreakerOpen) return 'failed';
    // If WebRTC is active, use its status
    if (streamMode === 'webrtc') {
        if (webrtcStatus === 'connected') return 'connected';
        if (webrtcStatus === 'error') return 'retrying'; // Or failed?
        return 'connecting';
    }
    // Fallback logic for MJPEG
    if (connectionState === 'connected' && isConnected) return 'connected';
    if (connectionState === 'retrying') return 'retrying';
    return 'connecting';
  });

  // Whether to show the image (MJPEG Mode)
  let showImage = $derived(streamMode === 'mjpeg' && isConnected && !imageError && imageRetryCount < MAX_IMAGE_RETRIES);

  $effect(() => {
    const currentStreamId = stream?.id;
    if (!currentStreamId) return;

    fetchStatus();
    if (stream.whisper_enabled) {
      fetchTranscripts();
    }

    return () => {
      if (imageRetryTimeout) {
        clearTimeout(imageRetryTimeout);
        imageRetryTimeout = null;
      }
    };
  });

  function handleImageError() {
    if (imageRetryCount >= MAX_IMAGE_RETRIES) {
      imageError = true;
      return;
    }
    imageError = true;
    imageRetryCount++;
    const delay = Math.min(2000 * Math.pow(2, imageRetryCount - 1), 32000);
    if (imageRetryTimeout) clearTimeout(imageRetryTimeout);
    imageRetryTimeout = setTimeout(() => {
      if (imageRetryCount < MAX_IMAGE_RETRIES) {
        imageError = false;
        imageCacheBuster = Date.now();
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
    // Also reset WebRTC if needed via key change or explicit method (not implemented yet)
  }
  
  function handleWebRTCStatus(status) {
    webrtcStatus = status;
  }

  async function handleForceRetry() {
    isForceRetrying = true;
    try {
      await control.forceRetry(stream.id);
      handleManualImageRetry();
    } catch (e) {
      console.error('Failed to force retry:', e);
    }
    isForceRetrying = false;
  }

  async function fetchStatus() {
    try {
      await status.get(stream.id);
    } catch (e) {
      console.error('Failed to fetch status:', e);
    }
  }

  async function fetchTranscripts() {
    try {
      await transcripts.get(stream.id, 10);
    } catch (e) {
      // Stream might not be running
    }
  }
  
  async function handleStart() {
    isLoading = true;
    try {
      await control.start(stream.id);
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
      handleManualImageRetry();
      streamEvents.clearTranscripts(stream.id);
      await fetchStatus();
    } catch (e) {
      console.error('Failed to restart stream:', e);
    }
    isLoading = false;
  }
  
  function toggleStreamMode() {
    streamMode = streamMode === 'webrtc' ? 'mjpeg' : 'webrtc';
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
      </div>
      
      <!-- Mode Toggle -->
      <button 
        onclick={toggleStreamMode}
        class="text-[10px] px-1.5 py-0.5 rounded border border-[var(--color-border)] hover:bg-[var(--color-bg-dark)] uppercase"
        title="Switch between WebRTC (Fast) and MJPEG (Compatible)"
      >
        {streamMode === 'webrtc' ? 'RTC' : 'JPG'}
      </button>

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

  <!-- Video Area -->
  <div class="relative aspect-video bg-black">
    {#if !isRunning}
       <div class="absolute inset-0 flex items-center justify-center">
          <div class="text-[var(--color-text-muted)] flex flex-col items-center">
             <Icon name="stop" size={24} class="mb-2 opacity-50"/>
             <span>Stream Stopped</span>
          </div>
       </div>
    {:else if streamMode === 'webrtc'}
      <!-- WebRTC Player -->
      <WebRTCPlayer 
        streamId={stream.id} 
        onStatusChange={handleWebRTCStatus}
      />
    {:else}
      <!-- Legacy MJPEG Player -->
      {#if showImage}
        <img
          src="{go2rtc.mjpegUrl(stream.id)}?t={imageCacheBuster}"
          alt={stream.name}
          class="stream-video w-full h-full object-contain"
          onerror={handleImageError}
          onload={handleImageLoad}
        />
      {:else}
        <!-- Loading / Error State for MJPEG -->
        <div class="absolute inset-0 flex items-center justify-center">
             {#if displayState === 'connecting'}
                <div class="animate-pulse text-[var(--color-warning)]">Connecting MJPEG...</div>
             {:else}
                <div class="text-[var(--color-warning)] flex flex-col items-center">
                    <Icon name="alert-triangle" size={24} class="mb-2"/>
                    <span>MJPEG Error</span>
                </div>
             {/if}
        </div>
      {/if}
    {/if}

    <!-- Whisper indicator -->
    {#if stream.whisper_enabled}
      <div class="absolute top-2 right-2 z-20 pointer-events-none">
        {#if hasWhisper}
          <Icon name="volume" size={18} class="text-[var(--color-success)] drop-shadow-md" />
        {:else}
          <Icon name="volume-x" size={18} class="text-[var(--color-text-muted)] drop-shadow-md" />
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
      <div class="flex gap-3">
        <button
          onclick={() => streamEvents.clearTranscripts(stream.id)}
          class="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-colors"
          title="Clear local transcript history"
        >
          Clear
        </button>
        <button
          onclick={() => showTranscripts = !showTranscripts}
          class="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          {showTranscripts ? 'Hide' : 'Show'} transcripts
        </button>
      </div>
    {/if}
  </div>
</div>
