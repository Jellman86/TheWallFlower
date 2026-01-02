<script>
  import { onMount } from 'svelte';
  import { faces } from '../services/api.js';
  import Icon from '../components/Icons.svelte';
  import FaceCard from '../components/FaceCard.svelte';
  import FaceEventsPanel from '../components/FaceEventsPanel.svelte';

  let faceList = $state([]);
  let isLoading = $state(true);
  let isLoadingMore = $state(false);
  let filter = $state('all'); // 'all', 'known', 'unknown'
  let total = $state(0);
  let hasMore = $state(false);
  let limit = 50;

  async function loadFaces(reset = true) {
    if (reset) {
      isLoading = true;
      faceList = [];
    } else {
      isLoadingMore = true;
    }

    try {
      const known = filter === 'all' ? null : (filter === 'known');
      const offset = reset ? 0 : faceList.length;
      const response = await faces.list(known, limit, offset);
      
      if (reset) {
        faceList = response.items;
      } else {
        faceList = [...faceList, ...response.items];
      }
      
      total = response.total;
      hasMore = response.has_more;
    } catch (e) {
      console.error('Failed to load faces:', e);
    } finally {
      isLoading = false;
      isLoadingMore = false;
    }
  }

  function handleLoadMore() {
    loadFaces(false);
  }

  $effect(() => {
    loadFaces(true);
  });
</script>

<div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
  <!-- Main Gallery -->
  <div class="lg:col-span-3 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold flex items-center gap-2">
          <Icon name="users" size={24} />
          Face Gallery
        </h2>
        <p class="text-xs text-[var(--color-text-muted)] mt-1">Showing {faceList.length} of {total} faces</p>
      </div>
      
      <!-- Filters -->
      <div class="flex bg-[var(--color-bg-dark)] rounded overflow-hidden text-sm">
        <button
          onclick={() => filter = 'all'}
          class="px-3 py-1.5 {filter === 'all' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'}"
        >
          All
        </button>
        <button
          onclick={() => filter = 'unknown'}
          class="px-3 py-1.5 {filter === 'unknown' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'}"
        >
          Unknown
        </button>
        <button
          onclick={() => filter = 'known'}
          class="px-3 py-1.5 {filter === 'known' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'}"
        >
          Known
        </button>
      </div>
    </div>

    <!-- Grid -->
    {#if isLoading}
      <div class="flex justify-center py-12">
        <Icon name="refresh" size={32} class="animate-spin text-[var(--color-text-muted)]" />
      </div>
    {:else if faceList.length === 0}
      <div class="text-center py-12 text-[var(--color-text-muted)]">
        <Icon name="user" size={48} class="mx-auto mb-4 opacity-50" />
        <p>No faces found matching your filter.</p>
      </div>
    {:else}
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
        {#each faceList as face (face.id)}
          <FaceCard 
            {face} 
            onUpdate={() => loadFaces(true)}
            onDelete={() => loadFaces(true)}
          />
        {/each}
      </div>

      {#if hasMore}
        <div class="flex justify-center pt-6">
          <button
            onclick={handleLoadMore}
            disabled={isLoadingMore}
            class="px-8 py-2 bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            {#if isLoadingMore}
              <Icon name="refresh" size={16} class="animate-spin" />
              Loading...
            {:else}
              Load More
            {/if}
          </button>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Sidebar -->
  <div class="lg:col-span-1 space-y-6">
    <div class="bg-[var(--color-bg-card)] p-4 rounded-xl border border-[var(--color-border)] h-fit">
      <FaceEventsPanel limit={15} />
    </div>
  </div>
</div>
