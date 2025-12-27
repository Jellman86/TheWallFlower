<script>
  import { status } from '../services/api.js';
  import Icon from './Icons.svelte';

  let { streams = [] } = $props();

  let allStatus = $state({});
  let isLoading = $state(true);

  // Derived stats
  let totalStreams = $derived(streams.length);
  let activeStreams = $derived(
    Object.values(allStatus).filter(s => s?.is_running).length
  );
  let connectedStreams = $derived(
    Object.values(allStatus).filter(s => s?.video_connected).length
  );
  let whisperEnabled = $derived(
    streams.filter(s => s.whisper_enabled).length
  );
  let whisperConnected = $derived(
    Object.values(allStatus).filter(s => s?.whisper_connected).length
  );

  // Fetch all stream statuses
  $effect(() => {
    if (streams.length > 0) {
      fetchAllStatus();
    }
  });

  async function fetchAllStatus() {
    isLoading = true;
    try {
      const result = await status.getAll();
      allStatus = result || {};
    } catch (e) {
      console.error('Failed to fetch status:', e);
    }
    isLoading = false;
  }
</script>

<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
  <!-- Total Streams -->
  <div class="bg-[var(--color-bg-card)] rounded-lg p-4 border border-[var(--color-border)]">
    <div class="flex items-center gap-3">
      <div class="p-2 bg-[var(--color-primary)]/20 rounded-lg">
        <Icon name="flower" size={24} class="text-[var(--color-primary)]" />
      </div>
      <div>
        <p class="text-2xl font-bold">{totalStreams}</p>
        <p class="text-xs text-[var(--color-text-muted)]">Total Streams</p>
      </div>
    </div>
  </div>

  <!-- Active Streams -->
  <div class="bg-[var(--color-bg-card)] rounded-lg p-4 border border-[var(--color-border)]">
    <div class="flex items-center gap-3">
      <div class="p-2 bg-[var(--color-success)]/20 rounded-lg">
        <Icon name="play" size={24} class="text-[var(--color-success)]" />
      </div>
      <div>
        <p class="text-2xl font-bold">
          {#if isLoading}
            <span class="text-[var(--color-text-muted)]">...</span>
          {:else}
            {connectedStreams}<span class="text-base text-[var(--color-text-muted)]">/{activeStreams}</span>
          {/if}
        </p>
        <p class="text-xs text-[var(--color-text-muted)]">Connected / Active</p>
      </div>
    </div>
  </div>

  <!-- Whisper Status -->
  <div class="bg-[var(--color-bg-card)] rounded-lg p-4 border border-[var(--color-border)]">
    <div class="flex items-center gap-3">
      <div class="p-2 bg-blue-500/20 rounded-lg">
        <Icon name="volume" size={24} class="text-blue-400" />
      </div>
      <div>
        <p class="text-2xl font-bold">
          {#if isLoading}
            <span class="text-[var(--color-text-muted)]">...</span>
          {:else}
            {whisperConnected}<span class="text-base text-[var(--color-text-muted)]">/{whisperEnabled}</span>
          {/if}
        </p>
        <p class="text-xs text-[var(--color-text-muted)]">Whisper Active</p>
      </div>
    </div>
  </div>

  <!-- Refresh -->
  <div class="bg-[var(--color-bg-card)] rounded-lg p-4 border border-[var(--color-border)]">
    <div class="flex items-center gap-3">
      <div class="p-2 bg-[var(--color-warning)]/20 rounded-lg">
        <Icon name="refresh" size={24} class="text-[var(--color-warning)]" />
      </div>
      <div class="flex-1">
        <button
          onclick={fetchAllStatus}
          disabled={isLoading}
          class="text-sm font-medium hover:text-[var(--color-primary)] transition-colors disabled:opacity-50"
        >
          Refresh Status
        </button>
        <p class="text-xs text-[var(--color-text-muted)]">Update all streams</p>
      </div>
    </div>
  </div>
</div>
