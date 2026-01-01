<script>
  import { status, transcripts, control } from '../services/api.js';
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

  // WebRTC State
  let webrtcStatus = $state('connecting'); // connecting, connected, error

  // Derived state
  let isRunning = $derived(streamStatus?.is_running ?? false);
  let hasWhisper = $derived(stream.whisper_enabled && streamStatus?.whisper_connected);

  // Enhanced connection state
  let retryCount = $derived(streamStatus?.retry_count ?? 0);
  let circuitBreakerOpen = $derived(streamStatus?.circuit_breaker_state === 'open');

  // Computed display state (WebRTC only)
  let displayState = $derived.by(() => {
    if (!isRunning) return 'stopped';
    if (circuitBreakerOpen) return 'failed';
    if (webrtcStatus === 'connected') return 'connected';
    if (webrtcStatus === 'error') return 'retrying';
    return 'connecting';
  });

  $effect(() => {
    const currentStreamId = stream?.id;
    if (!currentStreamId) return;

    fetchStatus();
    if (stream.whisper_enabled) {
      fetchTranscripts();
    }
  });

  function handleWebRTCStatus(status) {
    webrtcStatus = status;
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
      streamEvents.clearTranscripts(stream.id);
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

  <!-- Video Area -->
  <div class="relative aspect-video bg-black">
    {#if !isRunning}
       <div class="absolute inset-0 flex items-center justify-center">
          <div class="text-[var(--color-text-muted)] flex flex-col items-center">
             <Icon name="stop" size={24} class="mb-2 opacity-50"/>
             <span>Stream Stopped</span>
          </div>
       </div>
    {:else}
      <!-- WebRTC Player -->
      <WebRTCPlayer
        streamId={stream.id}
        onStatusChange={handleWebRTCStatus}
      />
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
