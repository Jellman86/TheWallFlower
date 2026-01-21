<script>
  import { untrack } from 'svelte';
  import { streams, healthCheck, fetchVersion, frigate } from './lib/services/api.js';
  import { streamEvents } from './lib/stores/streamEvents.svelte.js';
  import StreamCard from './lib/components/StreamCard.svelte';
  import SettingsModal from './lib/components/SettingsModal.svelte';
  import StatsPanel from './lib/components/StatsPanel.svelte';
  import Icon from './lib/components/Icons.svelte';
  import Faces from './lib/pages/Faces.svelte';
  import Tuning from './lib/pages/Tuning.svelte';

  // State
  let streamList = $state([]);
  let isLoading = $state(true);
  let error = $state('');
  let isHealthy = $state(false);
  let frigateUrl = $state('');

  // Version state
  let version = $state("0.3.0");
  let versionInfo = $state({ version: "0.3.0", base_version: "0.3.0", git_hash: "unknown" });

  // Modal state
  let showModal = $state(false);
  let editingStream = $state(null);

  // View state
  let viewMode = $state('grid'); // 'grid' or 'focus'
  let currentPage = $state('dashboard'); // 'dashboard' or 'faces'
  let focusedStream = $state(null);

  // Load streams on mount - use untrack to prevent re-runs
  let initialized = false;
  $effect(() => {
    if (!initialized) {
      initialized = true;
      untrack(() => {
        loadStreams();
        checkHealth();
        loadVersion();
        loadFrigateInfo();
        streamEvents.connect();
      });

      return () => {
        streamEvents.disconnect();
      };
    }
  });

  async function loadVersion() {
    const info = await fetchVersion();
    versionInfo = info;
    // Show clean version - hide "+unknown" suffix if git hash isn't available
    version = info.git_hash === "unknown" ? info.base_version : info.version;
  }

  async function checkHealth() {
    try {
      await healthCheck();
      isHealthy = true;
    } catch (e) {
      isHealthy = false;
    }
  }

  async function loadFrigateInfo() {
    try {
      const info = await frigate.getInfo();
      frigateUrl = info?.url || '';
    } catch (e) {
      frigateUrl = '';
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

  async function handleRefresh() {
    isLoading = true;
    error = '';
    try {
      await streams.refresh();
      streamList = await streams.list();
    } catch (e) {
      error = e.message || 'Failed to refresh streams';
    }
    isLoading = false;
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
  <header class="bg-[var(--color-bg-card)] border-b border-[var(--color-border)] px-4 py-3 md:px-6 md:py-4">
    <div class="flex flex-wrap items-center justify-between max-w-7xl mx-auto gap-2 md:gap-4">
      <div class="flex items-center gap-2 md:gap-3">
        <Icon name="flower" size={24} class="text-[var(--color-primary)] md:w-7 md:h-7" />
        <h1 class="text-lg md:text-xl font-bold truncate">TheWallflower</h1>
        <span class="hidden sm:inline-block text-xs text-[var(--color-text-muted)] bg-[var(--color-bg-hover)] px-2 py-0.5 rounded">
          NVR
        </span>
      </div>

      <div class="flex items-center gap-2 md:gap-4 ml-auto">
        <!-- Health indicator -->
        <div class="flex items-center gap-2 text-sm" title={isHealthy ? 'Backend Connected' : 'Backend Disconnected'}>
          <span class="status-dot {isHealthy ? 'connected' : 'disconnected'}"></span>
          <span class="hidden lg:inline text-[var(--color-text-muted)]">
            {isHealthy ? 'Backend Connected' : 'Backend Disconnected'}
          </span>
        </div>

        <!-- Navigation -->
        <div class="flex bg-[var(--color-bg-dark)] rounded overflow-hidden text-sm mx-1 md:mx-4">
          <button
            onclick={() => currentPage = 'dashboard'}
            class="px-3 py-2 md:px-4 {currentPage === 'dashboard' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'} transition-colors flex items-center gap-2"
            title="Dashboard"
          >
            <Icon name="grid" size={16} />
            <span class="hidden sm:inline">Dashboard</span>
          </button>
          <button
            onclick={() => currentPage = 'tuning'}
            class="px-3 py-2 md:px-4 {currentPage === 'tuning' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'} transition-colors flex items-center gap-2"
            title="Tuning"
          >
            <Icon name="settings" size={16} />
            <span class="hidden sm:inline">Tuning</span>
          </button>
          <button
            onclick={() => currentPage = 'faces'}
            class="px-3 py-2 md:px-4 {currentPage === 'faces' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'} transition-colors flex items-center gap-2"
            title="Faces"
          >
            <Icon name="users" size={16} />
            <span class="hidden sm:inline">Faces</span>
          </button>
        </div>

        <!-- View toggle (only on dashboard) -->
        {#if currentPage === 'dashboard'}
          <div class="flex bg-[var(--color-bg-dark)] rounded overflow-hidden hidden xs:flex">
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
        {/if}

        <!-- Refresh button -->
        <button
          onclick={handleRefresh}
          class="p-2 hover:bg-[var(--color-bg-hover)] rounded transition-colors"
          title="Refresh streams"
        >
          <Icon name="refresh" size={18} class={isLoading ? 'animate-spin' : ''} />
        </button>

        {#if frigateUrl}
          <a
            href={frigateUrl}
            target="_blank"
            rel="noopener"
            class="flex items-center gap-2 px-3 py-2 md:px-4 bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] rounded transition-colors text-sm"
            title="Open Frigate DVR"
          >
            <Icon name="video" size={18} />
            <span class="hidden md:inline">Frigate DVR</span>
          </a>
        {/if}
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

      {#if currentPage === 'tuning'}
        <Tuning />
      {:else if currentPage === 'faces'}
        <Faces />
      {:else}
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
              <h2 class="text-xl font-semibold mb-2">No Cameras Found</h2>
              <p class="text-[var(--color-text-muted)] mb-4">
                Make sure Frigate is running and has cameras configured.
              </p>
              {#if frigateUrl}
                <a
                  href={frigateUrl}
                  target="_blank"
                  rel="noopener"
                  class="flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] rounded transition-colors mx-auto"
                >
                  <Icon name="video" size={18} />
                  Open Frigate
                </a>
              {/if}
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
      {/if}
    </div>
  </main>

  <!-- Footer -->
  <footer class="bg-[var(--color-bg-card)] border-t border-[var(--color-border)] px-6 py-3">
    <div class="max-w-7xl mx-auto flex items-center justify-between text-sm text-[var(--color-text-muted)]">
      <span title={versionInfo.git_hash !== "unknown" ? `Git: ${versionInfo.git_hash}` : ""}>
        TheWallflower v{version}
      </span>
      <span>{streamList.length} stream{streamList.length !== 1 ? 's' : ''} configured</span>
    </div>
  </footer>
</div>

<!-- Settings Modal -->
<SettingsModal
  stream={editingStream}
  status={editingStream ? streamEvents.getStreamStatus(editingStream.id) : null}
  isOpen={showModal}
  onClose={handleModalClose}
  onSaved={handleSaved}
/>
