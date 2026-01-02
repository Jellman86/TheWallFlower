<script>
  import { onMount } from 'svelte';
  import { faces } from '../services/api.js';
  import Icon from './Icons.svelte';

  let { 
    faceId = null,
    streamId = null,
    limit = 20
  } = $props();

  let events = $state([]);
  let isLoading = $state(true);
  let selectedEvent = $state(null);

  async function loadEvents() {
    isLoading = true;
    try {
      events = await faces.listEvents(faceId, streamId, limit);
    } catch (e) {
      console.error('Failed to load face events:', e);
    }
    isLoading = false;
  }

  onMount(loadEvents);

  function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleString();
  }
</script>

<div class="space-y-4">
  <div class="flex items-center justify-between">
    <h3 class="font-bold flex items-center gap-2">
      <Icon name="history" size={18} />
      Recent Detections
    </h3>
    <button 
      onclick={loadEvents}
      class="p-1.5 hover:bg-[var(--color-bg-hover)] rounded-lg transition-colors"
      title="Refresh"
    >
      <Icon name="refresh" size={16} class={isLoading ? 'animate-spin' : ''} />
    </button>
  </div>

  {#if isLoading}
    <div class="flex justify-center py-8">
      <Icon name="refresh" size={24} class="animate-spin text-[var(--color-text-muted)]" />
    </div>
  {:else if events.length === 0}
    <p class="text-sm text-[var(--color-text-muted)] text-center py-8">
      No recent detection events.
    </p>
  {:else}
    <div class="grid grid-cols-1 gap-2 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
      {#each events as event (event.id)}
        <button
          onclick={() => selectedEvent = event}
          class="flex items-center gap-3 p-2 rounded-lg bg-[var(--color-bg-dark)]/50 border border-[var(--color-border)] hover:border-[var(--color-primary)] transition-all text-left"
        >
          <!-- Mini Thumbnail -->
          <div class="w-12 h-12 rounded bg-black overflow-hidden flex-shrink-0">
            {#if event.snapshot_path}
              <img 
                src={faces.snapshotUrl(event.snapshot_path)} 
                alt="Face" 
                class="w-full h-full object-cover"
              />
            {:else}
              <div class="w-full h-full flex items-center justify-center text-[var(--color-text-muted)]">
                <Icon name="user" size={20} />
              </div>
            {/if}
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex justify-between items-start">
              <span class="font-medium text-sm truncate">{event.face_name}</span>
              <span class="text-[10px] text-[var(--color-text-muted)]">
                {Math.round(event.confidence * 100)}%
              </span>
            </div>
            <div class="text-[10px] text-[var(--color-text-muted)]">
              {formatDate(event.timestamp)}
            </div>
          </div>
        </button>
      {/each}
    </div>
  {/if}
</div>

<!-- Snapshot Modal -->
{#if selectedEvent}
  <div 
    class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
    onclick={() => selectedEvent = null}
  >
    <div 
      class="bg-[var(--color-bg-card)] rounded-xl border border-[var(--color-border)] max-w-4xl w-full overflow-hidden shadow-2xl"
      onclick={e => e.stopPropagation()}
    >
      <div class="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
        <div>
          <h3 class="font-bold">{selectedEvent.face_name}</h3>
          <p class="text-xs text-[var(--color-text-muted)]">
            Detected on {formatDate(selectedEvent.timestamp)} ({Math.round(selectedEvent.confidence * 100)}% confidence)
          </p>
        </div>
        <button 
          onclick={() => selectedEvent = null}
          class="p-2 hover:bg-[var(--color-bg-hover)] rounded-lg transition-colors"
        >
          <Icon name="x" size={20} />
        </button>
      </div>
      
      <div class="relative bg-black aspect-video flex items-center justify-center">
        {#if selectedEvent.snapshot_path}
          <img 
            src={faces.snapshotUrl(selectedEvent.snapshot_path)} 
            alt="Full frame detection" 
            class="max-w-full max-h-full object-contain"
          />
        {:else}
          <div class="text-[var(--color-text-muted)] flex flex-col items-center gap-2">
            <Icon name="alert-circle" size={48} />
            <p>No full frame snapshot available for this event.</p>
          </div>
        {/if}
      </div>
      
      <div class="p-4 bg-[var(--color-bg-dark)] flex justify-end">
        <button 
          onclick={() => selectedEvent = null}
          class="px-4 py-2 bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] rounded-lg text-sm font-medium transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .custom-scrollbar::-webkit-scrollbar {
    width: 4px;
  }
  .custom-scrollbar::-webkit-scrollbar-track {
    background: transparent;
  }
  .custom-scrollbar::-webkit-scrollbar-thumb {
    background: var(--color-border);
    border-radius: 10px;
  }
</style>
