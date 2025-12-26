<script>
  import { video, status, transcripts, control } from '../services/api.js';
  import { Settings, Play, Square, RotateCw, Maximize2, Volume2, VolumeX } from 'lucide-svelte';

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
  let statusInterval = $state(null);
  let transcriptInterval = $state(null);

  // Derived state
  let isRunning = $derived(streamStatus?.is_running ?? false);
  let isConnected = $derived(streamStatus?.video_connected ?? false);
  let hasWhisper = $derived(stream.whisper_enabled && streamStatus?.whisper_connected);

  // Poll status and transcripts
  $effect(() => {
    if (stream?.id) {
      fetchStatus();
      if (stream.whisper_enabled) {
        fetchTranscripts();
      }

      // Poll every 2 seconds
      statusInterval = setInterval(fetchStatus, 2000);
      if (stream.whisper_enabled) {
        transcriptInterval = setInterval(fetchTranscripts, 3000);
      }
    }

    return () => {
      if (statusInterval) clearInterval(statusInterval);
      if (transcriptInterval) clearInterval(transcriptInterval);
    };
  });

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
    </div>
    <div class="flex items-center gap-1">
      {#if streamStatus?.fps}
        <span class="text-xs text-[var(--color-text-muted)]">{streamStatus.fps} fps</span>
      {/if}
      <button
        onclick={() => onFocus(stream)}
        class="p-1 hover:bg-[var(--color-bg-dark)] rounded transition-colors"
        title="Focus view"
      >
        <Maximize2 size={16} />
      </button>
      <button
        onclick={() => onEdit(stream)}
        class="p-1 hover:bg-[var(--color-bg-dark)] rounded transition-colors"
        title="Settings"
      >
        <Settings size={16} />
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
          <Volume2 size={18} class="text-[var(--color-success)]" />
        {:else}
          <VolumeX size={18} class="text-[var(--color-text-muted)]" />
        {/if}
      </div>
    {/if}
  </div>

  <!-- Transcript area (if enabled) -->
  {#if stream.whisper_enabled && showTranscripts}
    <div class="transcript-box h-24 overflow-y-auto p-2 bg-black/30 border-t border-[var(--color-border)]">
      {#if transcriptList.length > 0}
        {#each transcriptList as transcript}
          <p class="text-xs {transcript.is_final ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)] italic'}">
            {transcript.text}
          </p>
        {/each}
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
          <Play size={14} />
          Start
        </button>
      {:else}
        <button
          onclick={handleStop}
          disabled={isLoading}
          class="flex items-center gap-1 px-3 py-1 text-xs bg-[var(--color-danger)] hover:opacity-80 rounded transition-opacity disabled:opacity-50"
        >
          <Square size={14} />
          Stop
        </button>
        <button
          onclick={handleRestart}
          disabled={isLoading}
          class="flex items-center gap-1 px-3 py-1 text-xs bg-[var(--color-warning)] hover:opacity-80 rounded transition-opacity disabled:opacity-50"
        >
          <RotateCw size={14} />
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
