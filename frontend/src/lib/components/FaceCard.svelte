<script>
  import { untrack } from 'svelte';
  import { faces } from '../services/api.js';
  import Icon from './Icons.svelte';
  import FaceReviewModal from './FaceReviewModal.svelte';

  let {
    face,
    onUpdate = () => {},
    onDelete = () => {}
  } = $props();

  let isEditing = $state(false);
  let showReview = $state(false);
  let editName = $state('');
  let isLoading = $state(false);

  // Sync editName with face.name when face changes or when starting edit
  $effect(() => {
    untrack(() => {
      editName = face.name;
    });
  });

  async function handleSave() {
    isLoading = true;
    try {
      await faces.update(face.id, editName, true); // Mark as known when named
      isEditing = false;
      onUpdate();
    } catch (e) {
      console.error('Failed to update face:', e);
    }
    isLoading = false;
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to delete this face?')) return;
    
    isLoading = true;
    try {
      await faces.delete(face.id);
      onDelete();
    } catch (e) {
      console.error('Failed to delete face:', e);
    }
    isLoading = false;
  }
</script>

<div class="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg overflow-hidden flex flex-col group">
  <!-- Thumbnail -->
  <div class="relative aspect-square bg-[var(--color-bg-dark)] overflow-hidden cursor-pointer" onclick={() => showReview = true}>
    {#if face.thumbnail_path}
      <img
        src={faces.thumbnailUrl(face.id)}
        alt={face.name}
        class="w-full h-full object-cover transition-transform group-hover:scale-105"
        onerror={(e) => e.target.src = 'data:image/svg+xml;base64,...'} 
      />
    {:else}
      <div class="flex items-center justify-center h-full text-[var(--color-text-muted)]">
        <Icon name="user" size={48} />
      </div>
    {/if}
    
    <!-- Status Badge -->
    <div class="absolute top-2 right-2">
      <span class="px-2 py-0.5 text-xs rounded-full font-medium {face.is_known ? 'bg-[var(--color-success)]/80 text-white' : 'bg-[var(--color-warning)]/80 text-black'}">
        {face.is_known ? 'Known' : 'Unknown'}
      </span>
    </div>

    <!-- Review Overlay -->
    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
      <span class="px-3 py-1 bg-white/20 backdrop-blur-md rounded-full text-xs font-bold text-white border border-white/30">Review</span>
    </div>
  </div>

  <!-- Info -->
  <div class="p-3 flex-1 flex flex-col">
    {#if isEditing}
      <div class="flex gap-2 mb-2">
        <input
          type="text"
          bind:value={editName}
          class="flex-1 min-w-0 px-2 py-1 text-sm bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded focus:border-[var(--color-primary)] focus:outline-none"
          placeholder="Name..."
        />
        <button
          onclick={handleSave}
          disabled={isLoading}
          class="p-1 bg-[var(--color-success)] hover:bg-[var(--color-success)]/80 rounded text-white"
        >
          <Icon name="check" size={16} />
        </button>
      </div>
    {:else}
      <h3 class="font-semibold truncate mb-1 cursor-pointer hover:text-[var(--color-primary)] transition-colors" title={face.name} onclick={() => showReview = true}>{face.name}</h3>
    {/if}

    <p class="text-xs text-[var(--color-text-muted)] mb-3">
      Seen: {new Date(face.last_seen).toLocaleDateString()}
    </p>

    <!-- Actions -->
    <div class="mt-auto flex justify-between gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
      {#if !isEditing}
        <button
          onclick={() => showReview = true}
          class="flex-1 py-1 text-xs bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] rounded transition-colors"
        >
          Review
        </button>
        <button
          onclick={() => { editName = face.name; isEditing = true; }}
          class="px-2 py-1 text-xs bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] rounded transition-colors"
          title="Quick Rename"
        >
          <Icon name="settings" size={14} />
        </button>
        <button
          onclick={handleDelete}
          class="px-2 py-1 text-xs text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 rounded transition-colors"
        >
          <Icon name="trash" size={14} />
        </button>
      {/if}
    </div>
  </div>
</div>

<FaceReviewModal 
  {face}
  isOpen={showReview}
  onClose={() => showReview = false}
  onUpdated={onUpdate}
/>
