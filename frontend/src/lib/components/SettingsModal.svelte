<script>
  import { streams, control } from '../services/api.js';
  import Icon from './Icons.svelte';
  import AudioPreview from './AudioPreview.svelte';
  import AudioVisualizer from './AudioVisualizer.svelte';

  let {
    stream = null,
    status = null,
    isOpen = false,
    onClose = () => {},
    onSaved = () => {}
  } = $props();

  let name = $state('');
  let rtspUrl = $state('');
  let whisperEnabled = $state(false);
  let faceDetectionEnabled = $state(false);
  let saveTranscriptsToFile = $state(false);
  let transcriptFilePath = $state('');
  let isLoading = $state(false);
  let isTesting = $state(false);
  let error = $state('');
  let testResult = $state(null);

  // Audio tuning settings (null = use global defaults)
  let showAudioTuning = $state(false);
  let audioEnergyThreshold = $state(null);
  let audioVadEnabled = $state(null);
  let audioVadThreshold = $state(null);
  let audioVadOnset = $state(null);
  let audioVadOffset = $state(null);

  // Default values for display
  const DEFAULTS = {
    energy_threshold: 0.015,
    vad_enabled: true,
    vad_threshold: 0.6,
    vad_onset: 0.3,
    vad_offset: 0.3,
  };

  let isEditing = $derived(stream !== null);
  let title = $derived(isEditing ? 'Edit Stream' : 'Add Stream');

  // Reset form when stream changes
  $effect(() => {
    if (stream) {
      name = stream.name || '';
      rtspUrl = stream.rtsp_url || '';
      whisperEnabled = stream.whisper_enabled || false;
      faceDetectionEnabled = stream.face_detection_enabled || false;
      saveTranscriptsToFile = stream.save_transcripts_to_file || false;
      transcriptFilePath = stream.transcript_file_path || '';
      // Audio tuning settings
      audioEnergyThreshold = stream.audio_energy_threshold;
      audioVadEnabled = stream.audio_vad_enabled;
      audioVadThreshold = stream.audio_vad_threshold;
      audioVadOnset = stream.audio_vad_onset;
      audioVadOffset = stream.audio_vad_offset;
      // Show tuning section if any custom values are set
      showAudioTuning = audioEnergyThreshold !== null || audioVadEnabled !== null ||
                        audioVadThreshold !== null || audioVadOnset !== null || audioVadOffset !== null;
    } else {
      name = '';
      rtspUrl = '';
      whisperEnabled = false;
      faceDetectionEnabled = false;
      saveTranscriptsToFile = false;
      transcriptFilePath = '';
      // Reset audio tuning
      showAudioTuning = false;
      audioEnergyThreshold = null;
      audioVadEnabled = null;
      audioVadThreshold = null;
      audioVadOnset = null;
      audioVadOffset = null;
    }
    error = '';
    testResult = null;
  });

  async function handleTestConnection() {
    if (!rtspUrl.trim()) {
      error = 'Enter an RTSP URL to test';
      return;
    }

    isTesting = true;
    error = '';
    testResult = null;

    try {
      const result = await control.testConnection(rtspUrl.trim());
      testResult = result;
      if (!result.success) {
        error = result.error || 'Connection failed';
      }
    } catch (e) {
      error = e.message || 'Failed to test connection';
      testResult = { success: false, error: error };
    }

    isTesting = false;
  }

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

    // Basic RTSP URL validation
    if (!rtspUrl.trim().toLowerCase().startsWith('rtsp://')) {
      error = 'RTSP URL must start with rtsp://';
      return;
    }

    isLoading = true;

    try {
      const data = {
        name: name.trim(),
        rtsp_url: rtspUrl.trim(),
        whisper_enabled: whisperEnabled,
        face_detection_enabled: faceDetectionEnabled,
        save_transcripts_to_file: saveTranscriptsToFile,
        transcript_file_path: transcriptFilePath.trim() || null,
        // Audio tuning settings (null = use global defaults)
        audio_energy_threshold: audioEnergyThreshold,
        audio_vad_enabled: audioVadEnabled,
        audio_vad_threshold: audioVadThreshold,
        audio_vad_onset: audioVadOnset,
        audio_vad_offset: audioVadOffset,
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

  function resetAudioToDefaults() {
    audioEnergyThreshold = null;
    audioVadEnabled = null;
    audioVadThreshold = null;
    audioVadOnset = null;
    audioVadOffset = null;
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center modal-backdrop"
    onclick={handleBackdropClick}
  >
    <div class="bg-[var(--color-bg-card)] rounded-lg shadow-2xl w-full max-w-md mx-4 border border-[var(--color-border)]">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
        <h2 class="text-lg font-semibold">{title}</h2>
        <button
          onclick={onClose}
          class="p-1 hover:bg-[var(--color-bg-hover)] rounded transition-colors"
        >
          <Icon name="x" size={20} />
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
          <div class="flex gap-2">
            <input
              type="text"
              id="rtsp"
              bind:value={rtspUrl}
              placeholder="rtsp://user:pass@192.168.1.100:554/stream"
              class="flex-1 px-3 py-2 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded focus:border-[var(--color-primary)] focus:outline-none font-mono text-sm"
            />
            <button
              type="button"
              onclick={handleTestConnection}
              disabled={isTesting || !rtspUrl.trim()}
              class="px-3 py-2 text-sm bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded transition-colors disabled:opacity-50"
              title="Test connection"
            >
              {#if isTesting}
                <Icon name="refresh" size={16} class="animate-spin" />
              {:else}
                Test
              {/if}
            </button>
          </div>
          <p class="mt-1 text-xs text-[var(--color-text-muted)]">
            Include credentials if required: rtsp://user:pass@host:port/path
          </p>
          {#if testResult}
            <div class="mt-2 p-3 rounded text-xs {testResult.success ? 'bg-[var(--color-success)]/20' : 'bg-[var(--color-danger)]/20'}">
              {#if testResult.success}
                <div class="text-[var(--color-success)] font-medium mb-1">Connection successful</div>
                {#if testResult.metadata}
                  <div class="text-[var(--color-text-muted)] space-y-0.5">
                    <div>Resolution: {testResult.metadata.resolution}</div>
                    <div>Codec: {testResult.metadata.codec}</div>
                    {#if testResult.metadata.fps}
                      <div>FPS: {testResult.metadata.fps}</div>
                    {/if}
                    {#if testResult.metadata.bitrate_kbps}
                      <div>Bitrate: {testResult.metadata.bitrate_kbps} kbps</div>
                    {/if}
                    {#if testResult.metadata.has_audio}
                      <div>Audio: {testResult.metadata.audio_codec}</div>
                    {/if}
                  </div>
                {/if}
              {:else}
                <div class="text-[var(--color-danger)] font-medium mb-1">
                  {#if testResult.error_type === 'auth_failed'}
                    Authentication Failed
                  {:else if testResult.error_type === 'unreachable'}
                    Host Unreachable
                  {:else if testResult.error_type === 'timeout'}
                    Connection Timeout
                  {:else}
                    Connection Failed
                  {/if}
                </div>
                <div class="text-[var(--color-text-muted)]">{testResult.error}</div>

                <!-- Helpful hints based on error type -->
                {#if testResult.error_type === 'auth_failed'}
                  <div class="mt-2 text-[var(--color-text-muted)] italic">
                    Tip: Check your username and password in the URL
                  </div>
                {:else if testResult.error_type === 'unreachable'}
                  <div class="mt-2 text-[var(--color-text-muted)] italic">
                    Tip: Verify the IP address, port, and that the camera is powered on
                  </div>
                {:else if testResult.error_type === 'timeout'}
                  <div class="mt-2 text-[var(--color-text-muted)] italic">
                    Tip: The camera may be slow to respond or on a different network
                  </div>
                {/if}
              {/if}
            </div>
          {/if}
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

          {#if whisperEnabled}
            <div class="ml-7 space-y-3">
              <label class="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  bind:checked={saveTranscriptsToFile}
                  class="w-4 h-4 accent-[var(--color-primary)]"
                />
                <div>
                  <span class="text-sm font-medium">Save transcripts to file</span>
                  <p class="text-xs text-[var(--color-text-muted)]">
                    Write transcripts to the filesystem
                  </p>
                </div>
              </label>

              {#if saveTranscriptsToFile}
                <div>
                  <label for="transcript-path" class="block text-sm font-medium mb-1">File path (optional)</label>
                  <input
                    type="text"
                    id="transcript-path"
                    bind:value={transcriptFilePath}
                    placeholder="/data/transcripts/{name}.txt"
                    class="w-full px-3 py-2 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded focus:border-[var(--color-primary)] focus:outline-none font-mono text-xs"
                  />
                  <p class="mt-1 text-xs text-[var(--color-text-muted)]">
                    Leave empty for default: /data/transcripts/[stream-name].txt
                  </p>
                </div>
              {/if}

              <!-- Audio Tuning Section -->
              <div class="mt-4 pt-3 border-t border-[var(--color-border)]">
                <button
                  type="button"
                  onclick={() => showAudioTuning = !showAudioTuning}
                  class="flex items-center gap-2 text-sm font-medium text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                >
                  <Icon name={showAudioTuning ? 'chevron-down' : 'chevron-right'} size={16} />
                  Audio Tuning
                  {#if audioEnergyThreshold !== null || audioVadEnabled !== null || audioVadThreshold !== null}
                    <span class="text-xs px-1.5 py-0.5 bg-[var(--color-primary)]/20 text-[var(--color-primary)] rounded">Custom</span>
                  {/if}
                </button>

                {#if showAudioTuning}
                  <div class="mt-3 space-y-4 p-3 bg-[var(--color-bg-dark)] rounded border border-[var(--color-border)]">
                    
                    {#if isEditing && stream && status?.is_running}
                      <AudioVisualizer 
                        streamId={stream.id}
                        isRunning={true}
                        energyThreshold={audioEnergyThreshold ?? DEFAULTS.energy_threshold}
                        vadThreshold={audioVadThreshold ?? DEFAULTS.vad_threshold}
                      />
                    {/if}

                    <p class="text-xs text-[var(--color-text-muted)]">
                      Adjust audio filtering to reduce hallucinations. Leave blank to use global defaults.
                    </p>

                    <!-- Energy Threshold -->
                    <div>
                      <label class="block text-xs font-medium mb-1">
                        Energy Threshold
                        <span class="text-[var(--color-text-muted)]">
                          ({audioEnergyThreshold !== null ? audioEnergyThreshold.toFixed(3) : `default: ${DEFAULTS.energy_threshold}`})
                        </span>
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="0.1"
                        step="0.005"
                        value={audioEnergyThreshold ?? DEFAULTS.energy_threshold}
                        oninput={(e) => audioEnergyThreshold = parseFloat(e.target.value)}
                        class="w-full h-2 bg-[var(--color-bg-hover)] rounded-lg appearance-none cursor-pointer accent-[var(--color-primary)]"
                      />
                      <p class="mt-1 text-xs text-[var(--color-text-muted)]">
                        Skip audio below this RMS level. Higher = more filtering.
                      </p>
                    </div>

                    <!-- VAD Enabled -->
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={audioVadEnabled ?? DEFAULTS.vad_enabled}
                        onchange={(e) => audioVadEnabled = e.target.checked}
                        class="w-4 h-4 accent-[var(--color-primary)]"
                      />
                      <div>
                        <span class="text-xs font-medium">Silero VAD</span>
                        <span class="text-xs text-[var(--color-text-muted)] ml-1">
                          ({audioVadEnabled !== null ? (audioVadEnabled ? 'on' : 'off') : 'default'})
                        </span>
                      </div>
                    </label>

                    <!-- VAD Threshold -->
                    <div>
                      <label class="block text-xs font-medium mb-1">
                        VAD Threshold
                        <span class="text-[var(--color-text-muted)]">
                          ({audioVadThreshold !== null ? audioVadThreshold.toFixed(2) : `default: ${DEFAULTS.vad_threshold}`})
                        </span>
                      </label>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={audioVadThreshold ?? DEFAULTS.vad_threshold}
                        oninput={(e) => audioVadThreshold = parseFloat(e.target.value)}
                        class="w-full h-2 bg-[var(--color-bg-hover)] rounded-lg appearance-none cursor-pointer accent-[var(--color-primary)]"
                      />
                      <p class="mt-1 text-xs text-[var(--color-text-muted)]">
                        Speech probability threshold. Higher = stricter detection.
                      </p>
                    </div>

                    <!-- VAD Onset/Offset (collapsed) -->
                    <div class="grid grid-cols-2 gap-3">
                      <div>
                        <label class="block text-xs font-medium mb-1">VAD Onset</label>
                        <input
                          type="number"
                          min="0.1"
                          max="0.9"
                          step="0.05"
                          value={audioVadOnset ?? DEFAULTS.vad_onset}
                          oninput={(e) => audioVadOnset = parseFloat(e.target.value) || null}
                          class="w-full px-2 py-1 text-xs bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded"
                        />
                      </div>
                      <div>
                        <label class="block text-xs font-medium mb-1">VAD Offset</label>
                        <input
                          type="number"
                          min="0.1"
                          max="0.9"
                          step="0.05"
                          value={audioVadOffset ?? DEFAULTS.vad_offset}
                          oninput={(e) => audioVadOffset = parseFloat(e.target.value) || null}
                          class="w-full px-2 py-1 text-xs bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded"
                        />
                      </div>
                    </div>

                    <!-- Audio Preview and Reset -->
                    <div class="flex items-center justify-between pt-2 border-t border-[var(--color-border)]">
                      {#if isEditing && stream}
                        <AudioPreview streamId={stream.id} isRunning={status?.is_running ?? false} />
                      {:else}
                        <span class="text-xs text-[var(--color-text-muted)]">Save stream to preview audio</span>
                      {/if}
                      <button
                        type="button"
                        onclick={resetAudioToDefaults}
                        class="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-primary)] transition-colors"
                      >
                        Reset to defaults
                      </button>
                    </div>
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <label class="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              bind:checked={faceDetectionEnabled}
              class="w-4 h-4 accent-[var(--color-primary)]"
            />
            <div>
              <span class="text-sm font-medium">Enable Face Detection</span>
              <p class="text-xs text-[var(--color-text-muted)]">
                Detect and identify faces (1 FPS)
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
              <Icon name="trash" size={16} />
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
              <Icon name="save" size={16} />
              {isEditing ? 'Save' : 'Create'}
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
{/if}
