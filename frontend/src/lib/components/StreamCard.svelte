<script>
  import { video, status, transcripts, control, API_BASE } from '../services/api.js';
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

  // Derived state
  let isRunning = $derived(streamStatus?.is_running ?? false);
  let isConnected = $derived(streamStatus?.video_connected ?? false);
  let hasWhisper = $derived(stream.whisper_enabled && streamStatus?.whisper_connected);

  // Connect to SSE for real-time updates
  $effect(() => {
    if (stream?.id) {
      // Initial fetch for immediate data
      fetchStatus();
      if (stream.whisper_enabled) {
        fetchTranscripts();
      }

      // Connect to SSE
      connectSSE();
    }

    return () => {
      disconnectSSE();
    };
  });

  function connectSSE() {
    if (eventSource) {
      eventSource.close();
    }

    const url = `${API_BASE}/streams/${stream.id}/events`;
    eventSource = new EventSource(url);

    eventSource.addEventListener('status', (event) => {
      try {
        const data = JSON.parse(event.data);
        streamStatus = data.data;
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
        console.error('Stream error:', data.data?.error);
      } catch (e) {
        // Connection error, not a data error
      }
    });

    eventSource.onerror = () => {
      // SSE connection failed, try to reconnect after delay
      eventSource?.close();
      eventSource = null;

      // Reconnect after 5 seconds
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      reconnectTimeout = setTimeout(() => {
        if (stream?.id) connectSSE();
      }, 5000);
    };
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
      <span class="status-dot {isConnected ? 'connected' : isRunning ? 'connecting' : 'disconnected'}"></span>
      <h3 class="font-medium text-sm truncate">{stream.name}</h3>
      {#if streamStatus?.error}
        <span class="text-xs text-[var(--color-danger)]" title={streamStatus.error}>!</span>
      {/if}
    </div>
    <div class="flex items-center gap-2">
      <!-- Status indicators -->
      <div class="flex items-center gap-1 text-xs text-[var(--color-text-muted)]">
        {#if streamStatus?.fps}
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

  <!-- Video -->
  <div class="relative">
    {#if isConnected}
      <img
        src={video.streamUrl(stream.id)}
        alt={stream.name}
        class="stream-video"
      />
    {:else}
      <div class="stream-video flex items-center justify-center bg-black">
        <div class="text-center">
          {#if isRunning}
            <div class="animate-pulse text-[var(--color-warning)]">Connecting...</div>
          {:else if streamStatus?.error}
            <div class="text-[var(--color-danger)] text-sm">{streamStatus.error}</div>
          {:else}
            <div class="text-[var(--color-text-muted)]">Stream stopped</div>
          {/if}
        </div>
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
