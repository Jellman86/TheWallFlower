<script>
  import { streams } from '../services/api.js';
  import { X, Trash2, Save } from 'lucide-svelte';

  let {
    stream = null,
    isOpen = false,
    onClose = () => {},
    onSaved = () => {}
  } = $props();

  let name = $state('');
  let rtspUrl = $state('');
  let whisperEnabled = $state(false);
  let faceDetectionEnabled = $state(false);
  let isLoading = $state(false);
  let error = $state('');

  let isEditing = $derived(stream !== null);
  let title = $derived(isEditing ? 'Edit Stream' : 'Add Stream');

  // Reset form when stream changes
  $effect(() => {
    if (stream) {
      name = stream.name || '';
      rtspUrl = stream.rtsp_url || '';
      whisperEnabled = stream.whisper_enabled || false;
      faceDetectionEnabled = stream.face_detection_enabled || false;
    } else {
      name = '';
      rtspUrl = '';
      whisperEnabled = false;
      faceDetectionEnabled = false;
    }
    error = '';
  });

  async function handleSubmit(e) {
    e.preventDefault();
    error = '';

    if (!name.trim()) {
      error = 'Name is required';
      return;
    }
    if (!rtspUrl.trim()) {
      error = 'RTSP URL is required';
      return;
    }

    isLoading = true;

    try {
      const data = {
        name: name.trim(),
        rtsp_url: rtspUrl.trim(),
        whisper_enabled: whisperEnabled,
        face_detection_enabled: faceDetectionEnabled
      };

      if (isEditing) {
        await streams.update(stream.id, data);
      } else {
        await streams.create(data);
      }

      onSaved();
      onClose();
    } catch (e) {
      error = e.message || 'Failed to save stream';
    }

    isLoading = false;
  }

  async function handleDelete() {
    if (!confirm(`Are you sure you want to delete "${stream.name}"?`)) {
      return;
    }

    isLoading = true;
    try {
      await streams.delete(stream.id);
      onSaved();
      onClose();
    } catch (e) {
      error = e.message || 'Failed to delete stream';
    }
    isLoading = false;
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) {
      onClose();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      onClose();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center modal-backdrop"
    onclick={handleBackdropClick}
    role="dialog"
    aria-modal="true"
  >
    <div class="bg-[var(--color-bg-card)] rounded-lg shadow-2xl w-full max-w-md mx-4 border border-[var(--color-border)]">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <h2 class="text-lg font-semibold">{title}</h2>
        <button
          onclick={onClose}
          class="p-1 hover:bg-[var(--color-bg-hover)] rounded transition-colors"
        >
          <X size={20} />
        </button>
      </div>

      <!-- Form -->
      <form onsubmit={handleSubmit} class="p-6 space-y-4">
        {#if error}
          <div class="p-3 bg-[var(--color-danger)]/20 border border-[var(--color-danger)] rounded text-sm text-[var(--color-danger)]">
            {error}
          </div>
        {/if}

        <div>
          <label for="name" class="block text-sm font-medium mb-1">Stream Name</label>
          <input
            type="text"
            id="name"
            bind:value={name}
            placeholder="Front Door Camera"
            class="w-full px-3 py-2 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded focus:border-[var(--color-primary)] focus:outline-none"
          />
        </div>

        <div>
          <label for="rtsp" class="block text-sm font-medium mb-1">RTSP URL</label>
          <input
            type="text"
            id="rtsp"
            bind:value={rtspUrl}
            placeholder="rtsp://user:pass@192.168.1.100:554/stream"
            class="w-full px-3 py-2 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded focus:border-[var(--color-primary)] focus:outline-none font-mono text-sm"
          />
          <p class="mt-1 text-xs text-[var(--color-text-muted)]">
            Include credentials if required: rtsp://user:pass@host:port/path
          </p>
        </div>

        <div class="space-y-3">
          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              bind:checked={whisperEnabled}
              class="w-4 h-4 accent-[var(--color-primary)]"
            />
            <div>
              <span class="text-sm font-medium">Enable Speech-to-Text</span>
              <p class="text-xs text-[var(--color-text-muted)]">
                Transcribe audio using WhisperLive
              </p>
            </div>
          </label>

          <label class="flex items-center gap-3 cursor-pointer opacity-50">
            <input
              type="checkbox"
              bind:checked={faceDetectionEnabled}
              disabled
              class="w-4 h-4 accent-[var(--color-primary)]"
            />
            <div>
              <span class="text-sm font-medium">Enable Face Detection</span>
              <p class="text-xs text-[var(--color-text-muted)]">
                Coming soon - Detect and identify faces
              </p>
            </div>
          </label>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-between pt-4">
          {#if isEditing}
            <button
              type="button"
              onclick={handleDelete}
              disabled={isLoading}
              class="flex items-center gap-1 px-3 py-2 text-sm text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 rounded transition-colors disabled:opacity-50"
            >
              <Trash2 size={16} />
              Delete
            </button>
          {:else}
            <div></div>
          {/if}

          <div class="flex gap-2">
            <button
              type="button"
              onclick={onClose}
              class="px-4 py-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              class="flex items-center gap-1 px-4 py-2 text-sm bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] rounded transition-colors disabled:opacity-50"
            >
              <Save size={16} />
              {isEditing ? 'Save' : 'Create'}
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
{/if}
