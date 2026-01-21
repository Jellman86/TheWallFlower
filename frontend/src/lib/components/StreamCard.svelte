<script>
  import { status as statusApi, transcripts, control } from '../services/api.js';
  import { streamEvents } from '../stores/streamEvents.svelte.js';
  import Icon from './Icons.svelte';
  import WebRTCPlayer from './WebRTCPlayer.svelte';

  import AudioVisualizer from './AudioVisualizer.svelte';
  import TranscriptPanel from './TranscriptPanel.svelte';
  import FaceEventsPanel from './FaceEventsPanel.svelte';

  let {
    stream,
    onEdit = () => {},
    onFocus = () => {},
    focused = false
  } = $props();

  // Local state for view logic
  let activeView = $state('live'); // 'live', 'faces'

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
      await statusApi.get(stream.id);
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

<div class="bg-[var(--color-bg-card)] rounded-lg overflow-hidden shadow-lg border border-[var(--color-border)] {focused ? 'col-span-full h-full flex flex-col' : ''}">
  <!-- Header -->
  <div class="flex items-center justify-between px-4 py-2 bg-[var(--color-bg-hover)] flex-shrink-0">
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
      
      {#if !focused}
        <button
          onclick={() => onFocus(stream)}
          class="p-1 hover:bg-[var(--color-bg-dark)] rounded transition-colors"
          title="Focus view"
        >
          <Icon name="maximize" size={16} />
        </button>
      {/if}
      <button
        onclick={() => onEdit(stream)}
        class="p-1 hover:bg-[var(--color-bg-dark)] rounded transition-colors"
        title="Settings"
      >
        <Icon name="settings" size={16} />
      </button>
    </div>
  </div>

  <!-- Focused View (Tabbed) -->
  {#if focused}
    <div class="flex-1 flex flex-col md:flex-row min-h-0 border-t border-[var(--color-border)]">
      <!-- Sidebar / Tabs -->
      <div class="bg-[var(--color-bg-dark)] border-b md:border-b-0 md:border-r border-[var(--color-border)] flex md:flex-col shrink-0">
        <button
          onclick={() => activeView = 'live'}
          class="p-3 text-sm font-medium flex items-center gap-2 transition-colors { activeView === 'live' ? 'bg-[var(--color-bg-card)] text-[var(--color-primary)] border-b-2 md:border-b-0 md:border-l-2 border-[var(--color-primary)]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]' }"
        >
          <Icon name="video" size={18} />
          <span class="hidden md:inline">Live</span>
        </button>
        
        {#if stream.face_detection_enabled}
          <button
            onclick={() => activeView = 'faces'}
            class="p-3 text-sm font-medium flex items-center gap-2 transition-colors { activeView === 'faces' ? 'bg-[var(--color-bg-card)] text-[var(--color-primary)] border-b-2 md:border-b-0 md:border-l-2 border-[var(--color-primary)]' : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]' }"
          >
            <Icon name="user" size={18} />
            <span class="hidden md:inline">Faces</span>
          </button>
        {/if}
      </div>

      <div class="flex-1 overflow-hidden relative bg-black">
        {#if activeView === 'faces' && stream.face_detection_enabled}
          <div class="absolute inset-0 p-4 bg-[var(--color-bg-card)] overflow-y-auto">
            <FaceEventsPanel streamId={stream.id} />
          </div>
        {:else}
          <!-- LIVE VIEW -->
          <div class="flex flex-col h-full">
            <!-- Video Player -->
            <div class="relative bg-black flex-1 min-h-[300px]">
              {#if !isRunning}
                 <div class="absolute inset-0 flex items-center justify-center">
                    <div class="text-[var(--color-text-muted)] flex flex-col items-center">
                       <Icon name="stop" size={36} class="mb-2 opacity-50"/>
                       <span>Stream Stopped</span>
                    </div>
                 </div>
              {:else}
                <WebRTCPlayer streamId={stream.id} onStatusChange={handleWebRTCStatus} />
              {/if}
            </div>

            <!-- Controls & Transcript -->
            <div class="h-64 border-t border-[var(--color-border)] bg-[var(--color-bg-card)] flex flex-col">
               <div class="flex items-center gap-2 p-2 border-b border-[var(--color-border)]">
                 {#if !isRunning}
                  <button onclick={handleStart} class="px-2 py-1 text-xs rounded bg-[var(--color-success)] hover:opacity-80 transition-opacity">Start</button>
                 {:else}
                  <button onclick={handleStop} class="px-2 py-1 text-xs rounded bg-[var(--color-danger)] hover:opacity-80 transition-opacity">Stop</button>
                  <button onclick={handleRestart} class="px-2 py-1 text-xs rounded bg-[var(--color-warning)] hover:opacity-80 transition-opacity">Restart</button>
                 {/if}
               </div>
               <div class="flex-1 overflow-y-auto p-2">
                 <TranscriptPanel 
                   streamId={stream.id} 
                   streamName={stream.name} 
                   whisperEnabled={stream.whisper_enabled}
                   expanded={true}
                 />
               </div>
            </div>
          </div>
        {/if}
      </div>
    </div>

  {:else}
    <!-- GRID VIEW (Legacy Card) -->
    <div class="relative aspect-video bg-black group">
      {#if !isRunning}
         <div class="absolute inset-0 flex items-center justify-center">
            <div class="text-[var(--color-text-muted)] flex flex-col items-center">
               <Icon name="stop" size={24} class="mb-2 opacity-50"/>
               <span>Stopped</span>
            </div>
         </div>
      {:else}
        <WebRTCPlayer
          streamId={stream.id}
          onStatusChange={handleWebRTCStatus}
        />
      {/if}

      <!-- Whisper indicator -->
      <div class="absolute top-2 right-2 z-20 pointer-events-none flex flex-col gap-2">
        {#if stream.whisper_enabled}
          <div>
            {#if hasWhisper}
              <Icon name="volume" size={18} class="text-[var(--color-success)] drop-shadow-md" />
            {:else}
              <Icon name="volume-x" size={18} class="text-[var(--color-text-muted)] drop-shadow-md" />
            {/if}
          </div>
        {/if}
        {#if stream.face_detection_enabled}
          <div title="Face Detection Active">
            <Icon name="scan-face" size={18} class="text-[var(--color-primary)] drop-shadow-md" />
          </div>
        {/if}
      </div>

      <!-- Click to focus overlay -->
      <button 
        class="absolute inset-0 w-full h-full cursor-pointer bg-transparent"
        onclick={() => onFocus(stream)}
        title="Click to expand"
      ></button>
    </div>

    <!-- Transcript area (Grid View) -->
    {#if stream.whisper_enabled && showTranscripts}
      <div class="h-32 overflow-y-auto p-2 bg-black/30 border-t border-[var(--color-border)] text-xs">
        {#if transcriptList.length > 0}
          <div class="space-y-1">
            {#each transcriptList as transcript}
              <div class="flex gap-2">
                <span class="text-[var(--color-text-muted)] font-mono flex-shrink-0">
                  {new Date(transcript.created_at || Date.now()).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                </span>
                <span class="{transcript.is_final ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)] italic'}">
                  {transcript.text}
                </span>
              </div>
            {/each}
          </div>
        {:else}
          <p class="text-[var(--color-text-muted)] italic">Waiting for speech...</p>
        {/if}
      </div>
    {/if}

    <!-- Grid Controls -->
    <div class="flex items-center justify-between px-4 py-2 border-t border-[var(--color-border)] text-xs">
      <div class="flex gap-2">
        {#if !isRunning}
          <button onclick={handleStart} class="text-[var(--color-success)] hover:underline">Start</button>
        {:else}
          <button onclick={handleStop} class="text-[var(--color-danger)] hover:underline">Stop</button>
          <button onclick={handleRestart} class="text-[var(--color-warning)] hover:underline">Restart</button>
        {/if}
      </div>
    </div>
  {/if}
</div>
