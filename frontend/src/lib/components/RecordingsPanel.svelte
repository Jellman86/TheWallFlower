<script>
  import { onMount } from 'svelte';
  import { recordings } from '../services/api.js';
  import Icon from './Icons.svelte';

  let { streamId } = $props();

  let recordingList = $state([]);
  let dates = $state([]);
  let selectedDate = $state(new Date().toISOString().split('T')[0]);
  let isLoading = $state(false);
  let selectedRecording = $state(null);
  let videoPlayer = $state(null);

  // Load available dates on mount
  onMount(async () => {
    await loadDates();
    await loadRecordings();
  });

  async function loadDates() {
    try {
      dates = await recordings.listDates(streamId);
      // If selected date not in list and list not empty, select latest
      if (dates.length > 0 && !dates.includes(selectedDate)) {
        selectedDate = dates[dates.length - 1];
      }
    } catch (e) {
      console.error('Failed to load recording dates:', e);
    }
  }

  async function loadRecordings() {
    if (!selectedDate) return;
    
    isLoading = true;
    try {
      // Create time range for the selected day (UTC)
      // Note: backend expects ISO strings.
      // This simple logic assumes selectedDate is YYYY-MM-DD.
      const start = new Date(`${selectedDate}T00:00:00Z`);
      const end = new Date(`${selectedDate}T23:59:59Z`);
      
      recordingList = await recordings.list(streamId, start, end);
    } catch (e) {
      console.error('Failed to load recordings:', e);
    }
    isLoading = false;
  }

  function handleDateChange(e) {
    selectedDate = e.target.value;
    loadRecordings();
  }

  function playRecording(rec) {
    selectedRecording = rec;
    // Video player will auto-play due to autoplay attribute, but we can force it if needed
    if (videoPlayer) {
      videoPlayer.load();
      videoPlayer.play();
    }
  }

  function formatTime(isoString) {
    return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function formatDuration(seconds) {
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min}:${sec.toString().padStart(2, '0')}`;
  }

  function formatSize(bytes) {
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  }
</script>

<div class="flex flex-col h-full bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg overflow-hidden">
  
  <!-- Player Area -->
  <div class="flex-1 bg-black relative flex items-center justify-center min-h-[300px]">
    {#if selectedRecording}
      <video
        bind:this={videoPlayer}
        src={recordings.streamUrl(selectedRecording.id)}
        controls
        autoplay
        class="w-full h-full max-h-[60vh] object-contain"
      >
        <track kind="captions" />
      </video>
      <div class="absolute top-2 left-2 bg-black/60 text-white px-2 py-1 rounded text-sm pointer-events-none">
        {formatTime(selectedRecording.start_time)} - {formatTime(selectedRecording.end_time)}
      </div>
    {:else}
      <div class="text-[var(--color-text-muted)] flex flex-col items-center gap-2">
        <Icon name="video" size={48} />
        <p>Select a recording to play</p>
      </div>
    {/if}
  </div>

  <!-- Timeline / List Controls -->
  <div class="border-t border-[var(--color-border)] flex flex-col h-64">
    <!-- Toolbar -->
    <div class="p-2 border-b border-[var(--color-border)] flex items-center justify-between bg-[var(--color-bg-dark)]">
      <div class="flex items-center gap-2">
        <Icon name="calendar" size={16} class="text-[var(--color-text-muted)]" />
        <select 
          value={selectedDate} 
          onchange={handleDateChange}
          class="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded px-2 py-1 text-sm focus:outline-none focus:border-[var(--color-primary)]"
        >
          {#each dates as date}
            <option value={date}>{date}</option>
          {/each}
          {#if dates.length === 0}
            <option disabled>No recordings</option>
          {/if}
        </select>
        <button 
          onclick={loadDates}
          class="p-1 hover:bg-[var(--color-bg-hover)] rounded text-[var(--color-text-muted)]"
          title="Refresh"
        >
          <Icon name="refresh" size={14} class={isLoading ? 'animate-spin' : ''} />
        </button>
      </div>
      
      <div class="text-xs text-[var(--color-text-muted)]">
        {recordingList.length} clips ({formatSize(recordingList.reduce((acc, r) => acc + r.file_size_bytes, 0))})
      </div>
    </div>

    <!-- Scrollable List -->
    <div class="flex-1 overflow-y-auto p-2 space-y-1">
      {#if isLoading && recordingList.length === 0}
        <div class="flex items-center justify-center h-full text-[var(--color-text-muted)] text-sm">
          Loading...
        </div>
      {:else if recordingList.length === 0}
        <div class="flex items-center justify-center h-full text-[var(--color-text-muted)] text-sm">
          No recordings found for this date.
        </div>
      {:else}
        {#each recordingList as rec}
          <button
            onclick={() => playRecording(rec)}
            class="w-full flex items-center justify-between p-2 rounded text-sm transition-colors {selectedRecording?.id === rec.id ? 'bg-[var(--color-primary)] text-white' : 'hover:bg-[var(--color-bg-hover)] text-[var(--color-text)]'}"
          >
            <div class="flex items-center gap-3">
              <Icon name="play" size={12} class="opacity-50" />
              <span class="font-medium">{formatTime(rec.start_time)}</span>
              <span class="opacity-70 text-xs">({formatDuration(rec.duration_seconds)})</span>
            </div>
            <div class="opacity-60 text-xs">
              {formatSize(rec.file_size_bytes)}
            </div>
          </button>
        {/each}
      {/if}
    </div>
  </div>
</div>
