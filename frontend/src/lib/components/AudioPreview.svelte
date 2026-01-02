<script>
  import { audio } from '../services/api.js';
  import Icon from './Icons.svelte';

  let {
    streamId,
    isRunning = false
  } = $props();

  let isPlaying = $state(false);
  let audioElement = $state(null);
  let error = $state(null);

  function togglePlay() {
    if (!audioElement) return;

    if (isPlaying) {
      audioElement.pause();
      audioElement.src = '';
      isPlaying = false;
    } else {
      error = null;
      audioElement.src = audio.previewUrl(streamId);
      audioElement.play().catch(e => {
        error = 'Failed to play audio: ' + e.message;
        isPlaying = false;
      });
      isPlaying = true;
    }
  }

  function handleAudioError(e) {
    error = 'Audio stream error';
    isPlaying = false;
  }

  function handleAudioEnded() {
    isPlaying = false;
  }

  // Stop audio when component unmounts or stream stops
  $effect(() => {
    if (!isRunning && isPlaying && audioElement) {
      audioElement.pause();
      audioElement.src = '';
      isPlaying = false;
    }

    return () => {
      if (audioElement) {
        audioElement.pause();
        audioElement.src = '';
      }
    };
  });
</script>

<div class="audio-preview">
  <audio
    bind:this={audioElement}
    onerror={handleAudioError}
    onended={handleAudioEnded}
    class="hidden"
  ></audio>

  <button
    type="button"
    onclick={togglePlay}
    disabled={!isRunning}
    class="flex items-center gap-2 px-3 py-1.5 text-xs rounded transition-colors
           {isPlaying
             ? 'bg-[var(--color-danger)] hover:bg-[var(--color-danger)]/80'
             : 'bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] border border-[var(--color-border)]'}
           disabled:opacity-50 disabled:cursor-not-allowed"
    title={isRunning ? (isPlaying ? 'Stop audio preview' : 'Listen to processed audio') : 'Stream not running'}
  >
    <Icon name={isPlaying ? 'stop' : 'volume'} size={14} />
    {isPlaying ? 'Stop Preview' : 'Preview Audio'}
  </button>

  {#if error}
    <p class="mt-1 text-xs text-[var(--color-danger)]">{error}</p>
  {/if}

  {#if isPlaying}
    <p class="mt-1 text-xs text-[var(--color-text-muted)] animate-pulse">
      Playing processed audio...
    </p>
  {/if}
</div>
