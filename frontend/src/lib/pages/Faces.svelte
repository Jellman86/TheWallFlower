<script>
  import { onMount } from 'svelte';
  import { faces } from '../services/api.js';
  import Icon from '../components/Icons.svelte';
  import FaceCard from '../components/FaceCard.svelte';
  import FaceEventsPanel from '../components/FaceEventsPanel.svelte';

  let faceList = $state([]);
  let isLoading = $state(true);
  let filter = $state('all'); // 'all', 'known', 'unknown'

  async function loadFaces() {
    isLoading = true;
    try {
      const known = filter === 'all' ? null : (filter === 'known');
      faceList = await faces.list(known, 100);
    } catch (e) {
      console.error('Failed to load faces:', e);
    }
    isLoading = false;
  }

  $effect(() => {
    loadFaces();
  });
</script>

<div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
  <!-- Main Gallery -->
  <div class="lg:col-span-3 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold flex items-center gap-2">
        <Icon name="users" size={24} />
        Face Gallery
      </h2>
      
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
            onUpdate={loadFaces}
            onDelete={loadFaces}
          />
        {/each}
      </div>
    {/if}
  </div>

  <!-- Sidebar -->
  <div class="lg:col-span-1 space-y-6">
    <div class="bg-[var(--color-bg-card)] p-4 rounded-xl border border-[var(--color-border)] h-fit">
      <FaceEventsPanel limit={15} />
    </div>
  </div>
</div>
