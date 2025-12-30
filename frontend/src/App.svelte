<script>
  import { untrack } from 'svelte';
  import { streams, healthCheck } from './lib/services/api.js';
  import { streamEvents } from './lib/stores/streamEvents.svelte.js';
  import StreamCard from './lib/components/StreamCard.svelte';
  import SettingsModal from './lib/components/SettingsModal.svelte';
  import StatsPanel from './lib/components/StatsPanel.svelte';
  import Icon from './lib/components/Icons.svelte';

  // State
  let streamList = $state([]);
  let isLoading = $state(true);
  let error = $state('');
  let isHealthy = $state(false);

  // Modal state
  let showModal = $state(false);
  let editingStream = $state(null);

  // View state
  let viewMode = $state('grid'); // 'grid' or 'focus'
  let focusedStream = $state(null);

  // Load streams on mount - use untrack to prevent re-runs
  let initialized = false;
  $effect(() => {
    if (!initialized) {
      initialized = true;
      untrack(() => {
        loadStreams();
        checkHealth();
        streamEvents.connect();
      });

      return () => {
        streamEvents.disconnect();
      };
    }
  });

  async function checkHealth() {
    try {
      await healthCheck();
      isHealthy = true;
    } catch (e) {
      isHealthy = false;
    }
  }

  async function loadStreams() {
    isLoading = true;
    error = '';
    try {
      streamList = await streams.list();
    } catch (e) {
      error = e.message || 'Failed to load streams';
    }
    isLoading = false;
  }

  function handleAddStream() {
    editingStream = null;
    showModal = true;
  }

  function handleEditStream(stream) {
    editingStream = stream;
    showModal = true;
  }

  function handleFocusStream(stream) {
    focusedStream = stream;
    viewMode = 'focus';
  }

  function handleExitFocus() {
    focusedStream = null;
    viewMode = 'grid';
  }

  function handleModalClose() {
    showModal = false;
    editingStream = null;
  }

  function handleSaved() {
    loadStreams();
  }
</script>

<div class="min-h-screen flex flex-col">
  <!-- Header -->
  <header class="bg-[var(--color-bg-card)] border-b border-[var(--color-border)] px-6 py-4">
    <div class="flex items-center justify-between max-w-7xl mx-auto">
      <div class="flex items-center gap-3">
        <Icon name="flower" size={28} class="text-[var(--color-primary)]" />
        <h1 class="text-xl font-bold">TheWallflower</h1>
        <span class="text-xs text-[var(--color-text-muted)] bg-[var(--color-bg-hover)] px-2 py-0.5 rounded">
          NVR
        </span>
      </div>

      <div class="flex items-center gap-4">
        <!-- Health indicator -->
        <div class="flex items-center gap-2 text-sm">
          <span class="status-dot {isHealthy ? 'connected' : 'disconnected'}"></span>
          <span class="text-[var(--color-text-muted)]">
            {isHealthy ? 'Backend Connected' : 'Backend Disconnected'}
          </span>
        </div>

        <!-- View toggle -->
        <div class="flex bg-[var(--color-bg-dark)] rounded overflow-hidden">
          <button
            onclick={() => { viewMode = 'grid'; focusedStream = null; }}
            class="p-2 {viewMode === 'grid' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'} transition-colors"
            title="Grid view"
          >
            <Icon name="grid" size={18} />
          </button>
          <button
            onclick={() => viewMode = 'focus'}
            class="p-2 {viewMode === 'focus' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'} transition-colors"
            title="Focus view"
            disabled={!focusedStream}
          >
            <Icon name="maximize" size={18} />
          </button>
        </div>

        <!-- Refresh button -->
        <button
          onclick={loadStreams}
          class="p-2 hover:bg-[var(--color-bg-hover)] rounded transition-colors"
          title="Refresh streams"
        >
          <Icon name="refresh" size={18} class={isLoading ? 'animate-spin' : ''} />
        </button>

        <!-- Add stream button -->
        <button
          onclick={handleAddStream}
          class="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] rounded transition-colors"
        >
          <Icon name="plus" size={18} />
          Add Stream
        </button>
      </div>
    </div>
  </header>

  <!-- Main content -->
  <main class="flex-1 p-6">
    <div class="max-w-7xl mx-auto">
      {#if error}
        <div class="p-4 mb-6 bg-[var(--color-danger)]/20 border border-[var(--color-danger)] rounded-lg text-[var(--color-danger)]">
          {error}
          <button onclick={loadStreams} class="ml-2 underline">Retry</button>
        </div>
      {/if}

      {#if isLoading && streamList.length === 0}
        <div class="flex items-center justify-center h-64">
          <div class="text-center">
            <Icon name="refresh" size={32} class="animate-spin mx-auto mb-4 text-[var(--color-text-muted)]" />
            <p class="text-[var(--color-text-muted)]">Loading streams...</p>
          </div>
        </div>
      {:else if streamList.length === 0}
        <!-- Empty state -->
        <div class="flex items-center justify-center h-64">
          <div class="text-center">
            <Icon name="flower" size={48} class="mx-auto mb-4 text-[var(--color-text-muted)]" />
            <h2 class="text-xl font-semibold mb-2">No Streams Configured</h2>
            <p class="text-[var(--color-text-muted)] mb-4">
              Add your first RTSP camera stream to get started.
            </p>
            <button
              onclick={handleAddStream}
              class="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] rounded transition-colors mx-auto"
            >
              <Icon name="plus" size={18} />
              Add Your First Stream
            </button>
          </div>
        </div>
      {:else if viewMode === 'focus' && focusedStream}
        <!-- Focus view -->
        <div class="mb-4">
          <button
            onclick={handleExitFocus}
            class="text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            &larr; Back to grid
          </button>
        </div>
        <div class="max-w-4xl mx-auto">
          <StreamCard
            stream={focusedStream}
            onEdit={handleEditStream}
            onFocus={handleFocusStream}
            focused={true}
          />
        </div>
      {:else}
        <!-- Stats Panel -->
        <StatsPanel streams={streamList} />

        <!-- Grid view -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {#each streamList as stream (stream.id)}
            <StreamCard
              {stream}
              onEdit={handleEditStream}
              onFocus={handleFocusStream}
            />
          {/each}
        </div>
      {/if}
    </div>
  </main>

  <!-- Footer -->
  <footer class="bg-[var(--color-bg-card)] border-t border-[var(--color-border)] px-6 py-3">
    <div class="max-w-7xl mx-auto flex items-center justify-between text-sm text-[var(--color-text-muted)]">
      <span>TheWallflower v0.1.0</span>
      <span>{streamList.length} stream{streamList.length !== 1 ? 's' : ''} configured</span>
    </div>
  </footer>
</div>

<!-- Settings Modal -->
<SettingsModal
  stream={editingStream}
  isOpen={showModal}
  onClose={handleModalClose}
  onSaved={handleSaved}
/>
