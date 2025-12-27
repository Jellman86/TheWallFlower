<script>
  import { status, go2rtc } from '../services/api.js';
  import Icon from './Icons.svelte';

  let { streams = [] } = $props();

  let allStatus = $state({});
  let go2rtcStatus = $state(null);
  let isLoading = $state(true);
  let lastFetchedCount = $state(-1); // Track to prevent duplicate fetches

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

  // go2rtc status
  let go2rtcHealthy = $derived(go2rtcStatus?.status === 'healthy');
  let go2rtcStreamCount = $derived(go2rtcStatus?.stream_count ?? 0);

  // Fetch all stream statuses - only when stream count changes
  $effect(() => {
    const count = streams.length;
    if (count > 0 && count !== lastFetchedCount) {
      lastFetchedCount = count;
      fetchAllStatus();
    }
  });

  async function fetchAllStatus() {
    isLoading = true;
    try {
      const [statusResult, go2rtcResult] = await Promise.all([
        status.getAll(),
        go2rtc.getStatus().catch(() => null)
      ]);
      allStatus = statusResult || {};
      go2rtcStatus = go2rtcResult;
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

  <!-- go2rtc Status -->
  <div class="bg-[var(--color-bg-card)] rounded-lg p-4 border border-[var(--color-border)]">
    <div class="flex items-center gap-3">
      <div class="p-2 {go2rtcHealthy ? 'bg-[var(--color-success)]/20' : 'bg-[var(--color-warning)]/20'} rounded-lg">
        <Icon name="video" size={24} class="{go2rtcHealthy ? 'text-[var(--color-success)]' : 'text-[var(--color-warning)]'}" />
      </div>
      <div class="flex-1">
        <p class="text-2xl font-bold">
          {#if isLoading}
            <span class="text-[var(--color-text-muted)]">...</span>
          {:else if go2rtcStatus}
            {go2rtcStreamCount}<span class="text-base text-[var(--color-text-muted)]">/{totalStreams}</span>
          {:else}
            <span class="text-[var(--color-text-muted)]">-</span>
          {/if}
        </p>
        <p class="text-xs text-[var(--color-text-muted)]">
          {#if go2rtcHealthy}
            go2rtc Active
          {:else}
            go2rtc Offline
          {/if}
        </p>
      </div>
      <button
        onclick={fetchAllStatus}
        disabled={isLoading}
        class="p-1.5 hover:bg-[var(--color-bg-hover)] rounded transition-colors disabled:opacity-50"
        title="Refresh status"
      >
        <Icon name="refresh" size={16} class={isLoading ? 'animate-spin' : ''} />
      </button>
    </div>
  </div>
</div>
