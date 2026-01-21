<script>
  import { onMount } from 'svelte';
  import { faces } from '../services/api.js';
  import Icon from '../components/Icons.svelte';
  import FaceCard from '../components/FaceCard.svelte';
  import FaceEventsPanel from '../components/FaceEventsPanel.svelte';

  let faceList = $state([]);
  let groupedData = $state(null);
  let isLoading = $state(true);
  let isLoadingMore = $state(false);
  let filter = $state('all'); // 'all', 'known', 'unknown'
  let viewMode = $state('grid'); // 'grid' or 'grouped'
  let total = $state(0);
  let hasMore = $state(false);
  let limit = 50;
  let isPretraining = $state(false);

  // Merge mode state
  let mergeMode = $state(false);
  let selectedForMerge = $state(new Set());
  let isMerging = $state(false);
  let mergeError = $state('');

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

  async function loadGrouped() {
    isLoading = true;
    try {
      const knownOnly = filter === 'known';
      groupedData = await faces.getGrouped(knownOnly);
    } catch (e) {
      console.error('Failed to load grouped faces:', e);
    } finally {
      isLoading = false;
    }
  }

  function handleLoadMore() {
    loadFaces(false);
  }

  function toggleMergeMode() {
    mergeMode = !mergeMode;
    if (!mergeMode) {
      selectedForMerge = new Set();
      mergeError = '';
    }
  }

  async function handlePretrainScan() {
    isPretraining = true;
    try {
      const res = await fetch('/api/faces/pretrain/scan', { method: 'POST' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Failed to start pretrain scan');
      } else {
        alert('Pretrain scan started');
      }
    } catch (e) {
      alert('Failed to start pretrain scan');
    }
    isPretraining = false;
  }

  function toggleFaceSelection(faceId) {
    const newSet = new Set(selectedForMerge);
    if (newSet.has(faceId)) {
      newSet.delete(faceId);
    } else {
      newSet.add(faceId);
    }
    selectedForMerge = newSet;
  }

  async function handleMerge() {
    if (selectedForMerge.size < 2) {
      mergeError = 'Select at least 2 faces to merge';
      return;
    }

    const name = prompt('Enter name for the merged identity:');
    if (!name || !name.trim()) {
      return;
    }

    isMerging = true;
    mergeError = '';

    try {
      const result = await faces.merge(Array.from(selectedForMerge), name.trim());
      alert(`Merged ${result.merged_count} faces into "${result.name}" with ${result.total_embeddings} embeddings`);
      mergeMode = false;
      selectedForMerge = new Set();
      // Reload based on current view
      if (viewMode === 'grouped') {
        await loadGrouped();
      } else {
        await loadFaces(true);
      }
    } catch (e) {
      mergeError = e.message || 'Failed to merge faces';
    } finally {
      isMerging = false;
    }
  }

  async function handleMergeGroup(group) {
    if (group.face_count < 2) {
      return; // Nothing to merge
    }

    const confirmName = prompt(`Merge all ${group.face_count} faces into one identity.\n\nEnter name:`, group.name);
    if (!confirmName || !confirmName.trim()) {
      return;
    }

    isMerging = true;
    try {
      const faceIds = group.faces.map(f => f.id);
      const result = await faces.merge(faceIds, confirmName.trim());
      alert(`Merged ${result.merged_count} faces into "${result.name}" with ${result.total_embeddings} embeddings`);
      await loadGrouped();
    } catch (e) {
      alert('Failed to merge: ' + (e.message || 'Unknown error'));
    } finally {
      isMerging = false;
    }
  }

  // Switch view mode
  function setViewMode(mode) {
    viewMode = mode;
    if (mode === 'grouped') {
      loadGrouped();
    } else {
      loadFaces(true);
    }
  }

  $effect(() => {
    if (viewMode === 'grouped') {
      loadGrouped();
    } else {
      loadFaces(true);
    }
  });
</script>

<div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
  <!-- Main Gallery -->
  <div class="lg:col-span-3 space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-4">
      <div>
        <h2 class="text-xl font-bold flex items-center gap-2">
          <Icon name="users" size={24} />
          Face Gallery
        </h2>
        <p class="text-xs text-[var(--color-text-muted)] mt-1">
          {#if viewMode === 'grouped' && groupedData}
            {groupedData.total_groups} identities, {groupedData.total_faces} total faces
          {:else}
            Showing {faceList.length} of {total} faces
          {/if}
        </p>
      </div>

      <div class="flex items-center gap-2">
        <!-- View Mode Toggle -->
        <div class="flex bg-[var(--color-bg-dark)] rounded overflow-hidden text-sm">
          <button
            onclick={() => setViewMode('grid')}
            class="px-3 py-1.5 flex items-center gap-1 {viewMode === 'grid' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'}"
            title="Grid View"
          >
            <Icon name="grid" size={14} />
            Grid
          </button>
          <button
            onclick={() => setViewMode('grouped')}
            class="px-3 py-1.5 flex items-center gap-1 {viewMode === 'grouped' ? 'bg-[var(--color-primary)]' : 'hover:bg-[var(--color-bg-hover)]'}"
            title="Group by Name"
          >
            <Icon name="users" size={14} />
            Grouped
          </button>
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

        <!-- Merge Button (Grid mode only) -->
        {#if viewMode === 'grid'}
          <button
            onclick={toggleMergeMode}
            class="px-3 py-1.5 text-sm rounded flex items-center gap-1 transition-colors
                   {mergeMode
                     ? 'bg-[var(--color-warning)] text-black'
                     : 'bg-[var(--color-bg-dark)] hover:bg-[var(--color-bg-hover)]'}"
          >
            <Icon name="git-merge" size={14} />
            {mergeMode ? 'Cancel' : 'Merge'}
          </button>
        {/if}

        <button
          onclick={handlePretrainScan}
          disabled={isPretraining}
          class="px-3 py-1.5 text-sm rounded flex items-center gap-1 bg-[var(--color-bg-dark)] hover:bg-[var(--color-bg-hover)] disabled:opacity-50"
        >
          <Icon name="refresh" size={14} class={isPretraining ? 'animate-spin' : ''} />
          {isPretraining ? 'Scanning...' : 'Rescan Pretrain'}
        </button>
      </div>
    </div>

    <!-- Merge Mode Bar -->
    {#if mergeMode}
      <div class="bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 rounded-lg p-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <Icon name="git-merge" size={20} class="text-[var(--color-warning)]" />
          <div>
            <p class="font-medium">Merge Mode</p>
            <p class="text-xs text-[var(--color-text-muted)]">
              Select faces to merge into one identity ({selectedForMerge.size} selected)
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          {#if mergeError}
            <span class="text-xs text-[var(--color-danger)]">{mergeError}</span>
          {/if}
          <button
            onclick={handleMerge}
            disabled={selectedForMerge.size < 2 || isMerging}
            class="px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white rounded text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {#if isMerging}
              <Icon name="refresh" size={14} class="animate-spin" />
            {/if}
            Merge {selectedForMerge.size} Faces
          </button>
        </div>
      </div>
    {/if}

    <!-- Content -->
    {#if isLoading}
      <div class="flex justify-center py-12">
        <Icon name="refresh" size={32} class="animate-spin text-[var(--color-text-muted)]" />
      </div>
    {:else if viewMode === 'grouped'}
      <!-- Grouped View -->
      {#if !groupedData || groupedData.groups.length === 0}
        <div class="text-center py-12 text-[var(--color-text-muted)]">
          <Icon name="users" size={48} class="mx-auto mb-4 opacity-50" />
          <p>No faces found matching your filter.</p>
        </div>
      {:else}
        <div class="space-y-4">
          {#each groupedData.groups as group (group.name)}
            <div class="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg overflow-hidden">
              <!-- Group Header -->
              <div class="p-4 border-b border-[var(--color-border)] flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <!-- Primary Thumbnail -->
                  <div class="w-12 h-12 rounded-full overflow-hidden bg-[var(--color-bg-dark)] flex-shrink-0">
                    {#if group.primary_thumbnail}
                      <img
                        src={faces.thumbnailUrl(group.primary_face_id)}
                        alt={group.name}
                        class="w-full h-full object-cover"
                      />
                    {:else}
                      <div class="w-full h-full flex items-center justify-center">
                        <Icon name="user" size={24} class="text-[var(--color-text-muted)]" />
                      </div>
                    {/if}
                  </div>
                  <div>
                    <h3 class="font-semibold flex items-center gap-2">
                      {group.name}
                      {#if group.is_known}
                        <span class="px-2 py-0.5 text-xs rounded-full bg-[var(--color-success)]/20 text-[var(--color-success)]">Known</span>
                      {/if}
                    </h3>
                    <p class="text-xs text-[var(--color-text-muted)]">
                      {group.face_count} face records, {group.total_embeddings} embeddings
                    </p>
                  </div>
                </div>
                <div class="flex items-center gap-2">
                  {#if group.face_count > 1}
                    <button
                      onclick={() => handleMergeGroup(group)}
                      disabled={isMerging}
                      class="px-3 py-1.5 text-xs bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white rounded flex items-center gap-1 disabled:opacity-50"
                    >
                      <Icon name="git-merge" size={12} />
                      Merge All
                    </button>
                  {/if}
                </div>
              </div>

              <!-- Face Thumbnails -->
              {#if group.face_count > 1}
                <div class="p-4 bg-[var(--color-bg-dark)]/30">
                  <p class="text-xs text-[var(--color-text-muted)] mb-2">
                    {group.face_count} separate face records can be merged into one identity:
                  </p>
                  <div class="flex flex-wrap gap-2">
                    {#each group.faces as member (member.id)}
                      <div class="w-16 h-16 rounded-lg overflow-hidden bg-[var(--color-bg-dark)] relative group/thumb">
                        {#if member.thumbnail_path}
                          <img
                            src={faces.thumbnailUrl(member.id)}
                            alt="Face {member.id}"
                            class="w-full h-full object-cover"
                          />
                        {:else}
                          <div class="w-full h-full flex items-center justify-center">
                            <Icon name="user" size={20} class="text-[var(--color-text-muted)]" />
                          </div>
                        {/if}
                        <div class="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] text-center py-0.5">
                          {member.embedding_count} emb
                        </div>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    {:else}
      <!-- Grid View -->
      {#if faceList.length === 0}
        <div class="text-center py-12 text-[var(--color-text-muted)]">
          <Icon name="user" size={48} class="mx-auto mb-4 opacity-50" />
          <p>No faces found matching your filter.</p>
        </div>
      {:else}
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {#each faceList as face (face.id)}
            <div class="relative">
              {#if mergeMode}
                <!-- Selection Overlay -->
                <button
                  onclick={() => toggleFaceSelection(face.id)}
                  class="absolute inset-0 z-10 rounded-lg border-2 transition-colors
                         {selectedForMerge.has(face.id)
                           ? 'border-[var(--color-primary)] bg-[var(--color-primary)]/20'
                           : 'border-transparent hover:border-[var(--color-primary)]/50'}"
                >
                  {#if selectedForMerge.has(face.id)}
                    <div class="absolute top-2 left-2 w-6 h-6 bg-[var(--color-primary)] rounded-full flex items-center justify-center">
                      <Icon name="check" size={14} class="text-white" />
                    </div>
                  {/if}
                </button>
              {/if}
              <FaceCard
                {face}
                onUpdate={() => loadFaces(true)}
                onDelete={() => loadFaces(true)}
              />
            </div>
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
    {/if}
  </div>

  <!-- Sidebar -->
  <div class="lg:col-span-1 space-y-6">
    <div class="bg-[var(--color-bg-card)] p-4 rounded-xl border border-[var(--color-border)] h-fit">
      <FaceEventsPanel limit={15} />
    </div>
  </div>
</div>
