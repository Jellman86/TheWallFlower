<script>
  import { onMount } from 'svelte';
  import { faces } from '../services/api.js';
  import Icon from './Icons.svelte';

  let { 
    face,
    isOpen = false,
    onClose = () => {},
    onUpdated = () => {}
  } = $props();

  let embeddings = $state([]);
  let isLoading = $state(true);
  let editName = $state('');

  async function loadEmbeddings() {
    if (!face) return;
    isLoading = true;
    try {
      embeddings = await faces.listEmbeddings(face.id);
    } catch (e) {
      console.error('Failed to load embeddings:', e);
    }
    isLoading = false;
  }

  $effect(() => {
    if (isOpen && face) {
      editName = face.name;
      loadEmbeddings();
    }
  });

  async function handleSave() {
    try {
      await faces.update(face.id, editName, true);
      onUpdated();
      onClose();
    } catch (e) {
      console.error('Failed to update face:', e);
    }
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to delete this identity and all its embeddings?')) return;
    try {
      await faces.delete(face.id);
      onUpdated();
      onClose();
    } catch (e) {
      console.error('Failed to delete face:', e);
    }
  }
</script>

{#if isOpen && face}
  <div 
    class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
    onclick={onClose}
  >
    <div 
      class="bg-[var(--color-bg-card)] rounded-xl border border-[var(--color-border)] max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden shadow-2xl"
      onclick={e => e.stopPropagation()}
    >
      <!-- Header -->
      <div class="p-4 border-b border-[var(--color-border)] flex items-center justify-between bg-[var(--color-bg-hover)]">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-full bg-black overflow-hidden border border-[var(--color-border)]">
            <img src={faces.thumbnailUrl(face.id)} alt="" class="w-full h-full object-cover" />
          </div>
          <div>
            <h3 class="font-bold text-lg">Review Identity: {face.name}</h3>
            <p class="text-xs text-[var(--color-text-muted)]">ID: {face.id} • {face.embedding_count || 1} embeddings</p>
          </div>
        </div>
        <button 
          onclick={onClose}
          class="p-2 hover:bg-[var(--color-bg-dark)] rounded-lg transition-colors"
        >
          <Icon name="x" size={20} />
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- Identity Section -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="space-y-4">
            <h4 class="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Identity Details</h4>
            <div>
              <label for="review-name" class="block text-sm font-medium mb-1">Display Name</label>
              <input 
                id="review-name"
                type="text" 
                bind:value={editName}
                class="w-full px-3 py-2 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded-lg focus:border-[var(--color-primary)] outline-none transition-colors"
              />
            </div>
            <div class="flex gap-2">
              <button 
                onclick={handleSave}
                class="flex-1 px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white rounded-lg font-medium transition-colors"
              >
                Save Changes
              </button>
              <button 
                onclick={handleDelete}
                class="px-4 py-2 bg-[var(--color-danger)]/10 text-[var(--color-danger)] hover:bg-[var(--color-danger)]/20 rounded-lg transition-colors"
                title="Delete Identity"
              >
                <Icon name="trash" size={18} />
              </button>
            </div>
          </div>

          <div class="p-4 bg-[var(--color-bg-dark)]/50 rounded-xl border border-[var(--color-border)]">
            <h4 class="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] mb-3">Stats</h4>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-[var(--color-text-muted)]">First Seen</span>
                <span>{new Date(face.first_seen).toLocaleString()}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[var(--color-text-muted)]">Last Seen</span>
                <span>{new Date(face.last_seen).toLocaleString()}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-[var(--color-text-muted)]">Embeddings</span>
                <span>{face.embedding_count || 1}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Embeddings Grid -->
        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <h4 class="text-sm font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">Collected Samples</h4>
            <span class="text-xs text-[var(--color-text-muted)]">These samples are used to improve recognition.</span>
          </div>
          
          {#if isLoading}
            <div class="flex justify-center py-12">
              <Icon name="refresh" size={32} class="animate-spin text-[var(--color-text-muted)]" />
            </div>
          {:else if embeddings.length === 0}
            <div class="p-12 text-center border-2 border-dashed border-[var(--color-border)] rounded-xl text-[var(--color-text-muted)]">
              <Icon name="image" size={48} class="mx-auto mb-4 opacity-20" />
              <p>No sample crops available for this identity.</p>
            </div>
          {:else}
            <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3">
              {#each embeddings as emb (emb.id)}
                <div class="group relative aspect-square bg-black rounded-lg overflow-hidden border border-[var(--color-border)]">
                  {#if emb.image_path}
                    <img 
                      src={faces.embeddingUrl(emb.image_path)} 
                      alt="Sample" 
                      class="w-full h-full object-cover"
                    />
                  {:else}
                    <div class="w-full h-full flex items-center justify-center text-[var(--color-text-muted)]">
                      <Icon name="user" size={24} />
                    </div>
                  {/if}
                  <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span class="text-[10px] text-white bg-black/40 px-1 rounded">
                      {new Date(emb.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>

      <!-- Footer -->
      <div class="p-4 bg-[var(--color-bg-dark)] border-t border-[var(--color-border)] flex justify-end gap-3">
        <button 
          onclick={onClose}
          class="px-6 py-2 bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] rounded-lg text-sm font-medium transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
