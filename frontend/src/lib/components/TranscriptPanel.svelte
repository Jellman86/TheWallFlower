<script>
  import { transcripts as transcriptsApi, API_BASE } from '../services/api.js';
  import Icon from './Icons.svelte';

  let {
    streamId,
    streamName = 'Stream',
    whisperEnabled = true,
    expanded = false
  } = $props();

  let transcriptList = $state([]);
  let isLoading = $state(false);
  let searchQuery = $state('');
  let eventSource = $state(null);

  // Filtered transcripts
  let filteredTranscripts = $derived(
    searchQuery.trim()
      ? transcriptList.filter(t =>
          t.text.toLowerCase().includes(searchQuery.toLowerCase())
        )
      : transcriptList
  );

  // Connect to SSE for real-time transcripts
  $effect(() => {
    if (streamId && whisperEnabled) {
      fetchTranscripts();
      connectSSE();
    }
    return () => disconnectSSE();
  });

  function connectSSE() {
    if (eventSource) eventSource.close();

    const url = `${API_BASE}/streams/${streamId}/events`;
    eventSource = new EventSource(url);

    event_source.addEventListener('transcript', (event) => {
      try {
        const data = JSON.parse(event.data);
        const transcript = data.data;
        
        // Find if we already have this segment by ID (preferred) or start time
        const existingIndex = transcriptList.findIndex(t => 
          (transcript.id && t.id === transcript.id) || 
          Math.abs(t.start_time - transcript.start_time) < 0.1
        );

        if (existingIndex !== -1) {
          // Update existing segment
          transcriptList[existingIndex] = { ...transcriptList[existingIndex], ...transcript };
        } else {
          // New segment, add to front and enforce limit
          transcriptList = [transcript, ...transcriptList].slice(0, 100);
        }
      } catch (e) {
        console.error('Failed to parse transcript:', e);
      }
    });

    eventSource.onerror = () => {
      eventSource?.close();
      eventSource = null;
    };
  }

  function disconnectSSE() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
  }

  async function fetchTranscripts() {
    isLoading = true;
    try {
      const result = await transcriptsApi.get(streamId, 50);
      transcriptList = result.transcripts || [];
    } catch (e) {
      console.error('Failed to fetch transcripts:', e);
    }
    isLoading = false;
  }

  function formatTime(seconds) {
    if (!seconds && seconds !== 0) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  function formatTimestamp(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<div class="bg-[var(--color-bg-card)] rounded-lg border border-[var(--color-border)] {expanded ? 'h-96' : 'h-48'}">
  <!-- Header -->
  <div class="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)]">
    <div class="flex items-center gap-2">
      <Icon name="volume" size={16} class="text-[var(--color-text-muted)]" />
      <span class="text-sm font-medium">Transcripts</span>
      <span class="text-xs text-[var(--color-text-muted)]">({transcriptList.length})</span>
    </div>
    <div class="flex items-center gap-2">
      <!-- Search input -->
      <div class="relative">
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search..."
          class="w-32 text-xs px-2 py-1 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded focus:outline-none focus:border-[var(--color-primary)]"
        />
        {#if searchQuery}
          <button
            onclick={() => searchQuery = ''}
            class="absolute right-1 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <Icon name="x" size={12} />
          </button>
        {/if}
      </div>
      <!-- Clear -->
      <button
        onclick={() => { transcriptList = []; }}
        class="p-1 hover:bg-[var(--color-bg-hover)] rounded transition-colors text-[var(--color-text-muted)] hover:text-[var(--color-danger)]"
        title="Clear transcripts"
      >
        <Icon name="stop" size={14} />
      </button>
      <!-- Refresh -->
      <button
        onclick={fetchTranscripts}
        disabled={isLoading}
        class="p-1 hover:bg-[var(--color-bg-hover)] rounded transition-colors disabled:opacity-50"
        title="Refresh transcripts"
      >
        <Icon name="refresh" size={14} class={isLoading ? 'animate-spin' : ''} />
      </button>
    </div>
  </div>

  <!-- Transcript list -->
  <div class="overflow-y-auto {expanded ? 'h-80' : 'h-32'} p-2">
    {#if !whisperEnabled}
      <div class="flex items-center justify-center h-full text-[var(--color-text-muted)] text-sm">
        <Icon name="volume-x" size={20} class="mr-2" />
        Whisper not enabled for this stream
      </div>
    {:else if isLoading && transcriptList.length === 0}
      <div class="flex items-center justify-center h-full text-[var(--color-text-muted)] text-sm">
        <Icon name="refresh" size={16} class="animate-spin mr-2" />
        Loading transcripts...
      </div>
    {:else if filteredTranscripts.length === 0}
      <div class="flex items-center justify-center h-full text-[var(--color-text-muted)] text-sm italic">
        {searchQuery ? 'No matching transcripts' : 'Waiting for speech...'}
      </div>
    {:else}
      <div class="space-y-2">
        {#each filteredTranscripts as transcript, i}
          <div class="group flex gap-2 p-2 rounded hover:bg-[var(--color-bg-hover)] transition-colors {!transcript.is_final ? 'opacity-60' : ''}">
            <!-- Time indicator -->
            <div class="flex-shrink-0 text-xs text-[var(--color-text-muted)] font-mono w-16">
              {#if transcript.created_at}
                {formatTimestamp(transcript.created_at)}
              {:else}
                {formatTime(transcript.start_time)}
              {/if}
            </div>
            <!-- Text -->
            <div class="flex-1 min-w-0">
              <p class="text-sm {transcript.is_final ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)] italic'}">
                {transcript.text}
              </p>
              {#if transcript.start_time !== undefined && transcript.end_time !== undefined}
                <p class="text-xs text-[var(--color-text-muted)] mt-0.5">
                  {formatTime(transcript.start_time)} - {formatTime(transcript.end_time)}
                </p>
              {/if}
            </div>
            <!-- Status indicator -->
            <div class="flex-shrink-0">
              {#if transcript.is_final}
                <span class="inline-block w-2 h-2 rounded-full bg-[var(--color-success)]" title="Final"></span>
              {:else}
                <span class="inline-block w-2 h-2 rounded-full bg-[var(--color-warning)] animate-pulse" title="Interim"></span>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
