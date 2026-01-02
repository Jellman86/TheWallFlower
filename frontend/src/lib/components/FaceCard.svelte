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

  // Autocomplete state
  let knownNames = $state([]);
  let showSuggestions = $state(false);
  let filteredSuggestions = $state([]);
  let selectedSuggestion = $state(null);

  // Sync editName with face.name when face changes or when starting edit
  $effect(() => {
    untrack(() => {
      editName = face.name;
    });
  });

  async function startEdit() {
    editName = face.name;
    isEditing = true;
    selectedSuggestion = null;

    // Load known names for autocomplete
    try {
      knownNames = await faces.getKnownNames();
    } catch (e) {
      console.error('Failed to load known names:', e);
      knownNames = [];
    }
  }

  function handleInputChange(e) {
    editName = e.target.value;
    selectedSuggestion = null;

    // Filter suggestions
    if (editName.trim().length > 0) {
      const search = editName.toLowerCase();
      filteredSuggestions = knownNames.filter(
        kn => kn.name.toLowerCase().includes(search) && kn.name !== face.name
      );
      showSuggestions = filteredSuggestions.length > 0;
    } else {
      showSuggestions = false;
      filteredSuggestions = [];
    }
  }

  function selectSuggestion(suggestion) {
    editName = suggestion.name;
    selectedSuggestion = suggestion;
    showSuggestions = false;
  }

  async function handleSave() {
    if (!editName.trim()) return;

    isLoading = true;
    try {
      // If we selected an existing person, use assignToExisting (which merges)
      if (selectedSuggestion) {
        const result = await faces.assignToExisting(face.id, editName.trim());
        if (result.merged_count > 1) {
          // Face was merged
          console.log(`Merged into ${result.name} with ${result.total_embeddings} embeddings`);
        }
      } else {
        // Check if the name matches an existing known face
        const matchingKnown = knownNames.find(
          kn => kn.name.toLowerCase() === editName.trim().toLowerCase() && kn.name !== face.name
        );

        if (matchingKnown) {
          // Name matches existing - ask to merge
          const confirmMerge = confirm(
            `A person named "${matchingKnown.name}" already exists.\n\n` +
            `Would you like to merge this face into their identity?\n\n` +
            `Click OK to merge, or Cancel to use a different name.`
          );

          if (confirmMerge) {
            await faces.assignToExisting(face.id, matchingKnown.name);
          } else {
            isLoading = false;
            return;
          }
        } else {
          // New name or same name - just update
          await faces.update(face.id, editName.trim(), true);
        }
      }

      isEditing = false;
      showSuggestions = false;
      selectedSuggestion = null;
      onUpdate();
    } catch (e) {
      console.error('Failed to update face:', e);
      alert('Failed to save: ' + (e.message || 'Unknown error'));
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

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      isEditing = false;
      showSuggestions = false;
    } else if (e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
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

    <!-- Embedding Count Badge -->
    {#if face.embedding_count > 1}
      <div class="absolute top-2 left-2">
        <span class="px-2 py-0.5 text-xs rounded-full font-medium bg-black/60 text-white">
          {face.embedding_count} emb
        </span>
      </div>
    {/if}

    <!-- Review Overlay -->
    <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
      <span class="px-3 py-1 bg-white/20 backdrop-blur-md rounded-full text-xs font-bold text-white border border-white/30">Review</span>
    </div>
  </div>

  <!-- Info -->
  <div class="p-3 flex-1 flex flex-col">
    {#if isEditing}
      <div class="relative mb-2">
        <div class="flex gap-2">
          <input
            type="text"
            bind:value={editName}
            oninput={handleInputChange}
            onkeydown={handleKeydown}
            onfocus={() => { if (filteredSuggestions.length > 0) showSuggestions = true; }}
            class="flex-1 min-w-0 px-2 py-1 text-sm bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded focus:border-[var(--color-primary)] focus:outline-none"
            placeholder="Enter name..."
          />
          <button
            type="button"
            onclick={handleSave}
            disabled={isLoading || !editName.trim()}
            class="p-1 bg-[var(--color-success)] hover:bg-[var(--color-success)]/80 rounded text-white disabled:opacity-50"
          >
            <Icon name="check" size={16} />
          </button>
          <button
            type="button"
            onclick={() => { isEditing = false; showSuggestions = false; }}
            class="p-1 bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] rounded"
          >
            <Icon name="x" size={16} />
          </button>
        </div>

        <!-- Autocomplete Dropdown -->
        {#if showSuggestions && filteredSuggestions.length > 0}
          <div class="absolute top-full left-0 right-0 mt-1 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
            <div class="px-2 py-1 text-xs text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
              Assign to existing person:
            </div>
            {#each filteredSuggestions as suggestion (suggestion.face_id)}
              <button
                type="button"
                onclick={() => selectSuggestion(suggestion)}
                class="w-full px-2 py-2 flex items-center gap-2 hover:bg-[var(--color-bg-hover)] text-left"
              >
                <div class="w-8 h-8 rounded-full overflow-hidden bg-[var(--color-bg-dark)] flex-shrink-0">
                  {#if suggestion.thumbnail_path}
                    <img
                      src={faces.thumbnailUrl(suggestion.face_id)}
                      alt={suggestion.name}
                      class="w-full h-full object-cover"
                    />
                  {:else}
                    <div class="w-full h-full flex items-center justify-center">
                      <Icon name="user" size={16} class="text-[var(--color-text-muted)]" />
                    </div>
                  {/if}
                </div>
                <div class="flex-1 min-w-0">
                  <p class="font-medium text-sm truncate">{suggestion.name}</p>
                  <p class="text-xs text-[var(--color-text-muted)]">{suggestion.embedding_count} embeddings</p>
                </div>
                <Icon name="git-merge" size={14} class="text-[var(--color-primary)] flex-shrink-0" />
              </button>
            {/each}
          </div>
        {/if}

        <!-- Selected Suggestion Indicator -->
        {#if selectedSuggestion}
          <div class="mt-1 px-2 py-1 bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30 rounded text-xs flex items-center gap-1">
            <Icon name="git-merge" size={12} class="text-[var(--color-primary)]" />
            Will merge into "{selectedSuggestion.name}"
          </div>
        {/if}
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
          type="button"
          onclick={() => showReview = true}
          class="flex-1 py-1 text-xs bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] rounded transition-colors"
        >
          Review
        </button>
        <button
          type="button"
          onclick={startEdit}
          class="px-2 py-1 text-xs bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] rounded transition-colors"
          title="Rename / Assign to Person"
        >
          <Icon name="settings" size={14} />
        </button>
        <button
          type="button"
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
