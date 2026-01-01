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

  // Tab navigation
  let activeTab = $state('general');

  let name = $state('');
  let rtspUrl = $state('');
  let whisperEnabled = $state(false);
  let faceDetectionEnabled = $state(false);
  let faceDetectionInterval = $state(1);
  let saveTranscriptsToFile = $state(false);
  let transcriptFilePath = $state('');
  let recordingEnabled = $state(false);
  let recordingRetentionDays = $state(7);
  let isLoading = $state(false);
  let isTesting = $state(false);
  let error = $state('');
  let testResult = $state(null);

  // Audio tuning settings (null = use global defaults)
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
  let title = $derived(isEditing ? 'Stream Settings' : 'Add New Stream');

  // Check if audio has custom settings
  let hasCustomAudio = $derived(
    audioEnergyThreshold !== null || audioVadEnabled !== null ||
    audioVadThreshold !== null || audioVadOnset !== null || audioVadOffset !== null
  );

  // Reset form when stream changes
  $effect(() => {
    if (stream) {
      name = stream.name || '';
      rtspUrl = stream.rtsp_url || '';
      whisperEnabled = stream.whisper_enabled || false;
      faceDetectionEnabled = stream.face_detection_enabled || false;
      faceDetectionInterval = stream.face_detection_interval || 1;
      saveTranscriptsToFile = stream.save_transcripts_to_file || false;
      transcriptFilePath = stream.transcript_file_path || '';
      recordingEnabled = stream.recording_enabled || false;
      recordingRetentionDays = stream.recording_retention_days || 7;
      // Audio tuning settings
      audioEnergyThreshold = stream.audio_energy_threshold;
      audioVadEnabled = stream.audio_vad_enabled;
      audioVadThreshold = stream.audio_vad_threshold;
      audioVadOnset = stream.audio_vad_onset;
      audioVadOffset = stream.audio_vad_offset;
    } else {
      name = '';
      rtspUrl = '';
      whisperEnabled = false;
      faceDetectionEnabled = false;
      faceDetectionInterval = 1;
      saveTranscriptsToFile = false;
      transcriptFilePath = '';
      recordingEnabled = false;
      recordingRetentionDays = 7;
      // Reset audio tuning
      audioEnergyThreshold = null;
      audioVadEnabled = null;
      audioVadThreshold = null;
      audioVadOnset = null;
      audioVadOffset = null;
    }
    error = '';
    testResult = null;
    activeTab = 'general';
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
      activeTab = 'general';
      return;
    }
    if (!rtspUrl.trim()) {
      error = 'RTSP URL is required';
      activeTab = 'general';
      return;
    }

    // Basic RTSP URL validation
    if (!rtspUrl.trim().toLowerCase().startsWith('rtsp://')) {
      error = 'RTSP URL must start with rtsp://';
      activeTab = 'general';
      return;
    }

    isLoading = true;

    try {
      const data = {
        name: name.trim(),
        rtsp_url: rtspUrl.trim(),
        whisper_enabled: whisperEnabled,
        face_detection_enabled: faceDetectionEnabled,
        face_detection_interval: parseInt(faceDetectionInterval) || 1,
        save_transcripts_to_file: saveTranscriptsToFile,
        transcript_file_path: transcriptFilePath.trim() || null,
        recording_enabled: recordingEnabled,
        recording_retention_days: parseInt(recordingRetentionDays) || 7,
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

  const tabs = [
    { id: 'general', label: 'General', icon: 'settings' },
    { id: 'features', label: 'Features', icon: 'sliders' },
    { id: 'audio', label: 'Audio', icon: 'volume' },
  ];
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div
    class="fixed inset-0 z-50 flex items-center justify-center p-4 modal-backdrop"
    onclick={handleBackdropClick}
  >
    <div class="bg-[var(--color-bg-card)] rounded-xl shadow-2xl w-full max-w-lg flex flex-col max-h-[90vh] border border-[var(--color-border)] overflow-hidden">
      <!-- Header (sticky) -->
      <div class="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)] bg-[var(--color-bg-card)]">
        <div>
          <h2 class="text-lg font-semibold">{title}</h2>
          {#if isEditing && stream}
            <p class="text-xs text-[var(--color-text-muted)] mt-0.5">ID: {stream.id}</p>
          {/if}
        </div>
        <button
          onclick={onClose}
          class="p-2 hover:bg-[var(--color-bg-hover)] rounded-lg transition-colors"
          aria-label="Close"
        >
          <Icon name="x" size={20} />
        </button>
      </div>

      <!-- Tab Navigation -->
      <div class="flex-shrink-0 flex border-b border-[var(--color-border)] bg-[var(--color-bg-dark)]/50">
        {#each tabs as tab}
          <button
            type="button"
            onclick={() => activeTab = tab.id}
            class="flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-colors relative
              {activeTab === tab.id
                ? 'text-[var(--color-primary)]'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'}"
          >
            <Icon name={tab.icon} size={16} />
            {tab.label}
            {#if tab.id === 'audio' && hasCustomAudio}
              <span class="absolute top-2 right-2 w-2 h-2 bg-[var(--color-primary)] rounded-full"></span>
            {/if}
            {#if activeTab === tab.id}
              <span class="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-primary)]"></span>
            {/if}
          </button>
        {/each}
      </div>

      <!-- Form (scrollable) -->
      <form onsubmit={handleSubmit} class="flex-1 flex flex-col min-h-0">
        <div class="flex-1 overflow-y-auto p-6">
          {#if error}
            <div class="mb-4 p-3 bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30 rounded-lg text-sm text-[var(--color-danger)] flex items-start gap-2">
              <Icon name="alert-circle" size={18} class="flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          {/if}

          <!-- General Tab -->
          {#if activeTab === 'general'}
            <div class="space-y-5">
              <div>
                <label for="name" class="block text-sm font-medium mb-2">Stream Name</label>
                <input
                  type="text"
                  id="name"
                  bind:value={name}
                  placeholder="Front Door Camera"
                  class="w-full px-4 py-2.5 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded-lg focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)] focus:outline-none transition-colors"
                />
              </div>

              <div>
                <label for="rtsp" class="block text-sm font-medium mb-2">RTSP URL</label>
                <div class="flex gap-2">
                  <input
                    type="text"
                    id="rtsp"
                    bind:value={rtspUrl}
                    placeholder="rtsp://user:pass@192.168.1.100:554/stream"
                    class="flex-1 px-4 py-2.5 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded-lg focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)] focus:outline-none font-mono text-sm transition-colors"
                  />
                  <button
                    type="button"
                    onclick={handleTestConnection}
                    disabled={isTesting || !rtspUrl.trim()}
                    class="px-4 py-2.5 text-sm font-medium bg-[var(--color-bg-hover)] hover:bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Test connection"
                  >
                    {#if isTesting}
                      <Icon name="refresh" size={16} class="animate-spin" />
                    {:else}
                      Test
                    {/if}
                  </button>
                </div>
                <p class="mt-2 text-xs text-[var(--color-text-muted)]">
                  Include credentials if required: rtsp://user:pass@host:port/path
                </p>

                {#if testResult}
                  <div class="mt-3 p-4 rounded-lg text-sm {testResult.success ? 'bg-[var(--color-success)]/10 border border-[var(--color-success)]/30' : 'bg-[var(--color-danger)]/10 border border-[var(--color-danger)]/30'}">
                    {#if testResult.success}
                      <div class="flex items-center gap-2 text-[var(--color-success)] font-medium mb-2">
                        <Icon name="check" size={16} />
                        Connection Successful
                      </div>
                      {#if testResult.metadata}
                        <div class="grid grid-cols-2 gap-2 text-xs text-[var(--color-text-muted)]">
                          <div>Resolution: <span class="text-[var(--color-text)]">{testResult.metadata.resolution}</span></div>
                          <div>Codec: <span class="text-[var(--color-text)]">{testResult.metadata.codec}</span></div>
                          {#if testResult.metadata.fps}
                            <div>FPS: <span class="text-[var(--color-text)]">{testResult.metadata.fps}</span></div>
                          {/if}
                          {#if testResult.metadata.has_audio}
                            <div>Audio: <span class="text-[var(--color-text)]">{testResult.metadata.audio_codec}</span></div>
                          {/if}
                        </div>
                      {/if}
                    {:else}
                      <div class="flex items-center gap-2 text-[var(--color-danger)] font-medium mb-2">
                        <Icon name="x" size={16} />
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
                      <p class="text-xs text-[var(--color-text-muted)]">{testResult.error}</p>
                    {/if}
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <!-- Features Tab -->
          {#if activeTab === 'features'}
            <div class="space-y-4">
              <!-- Speech-to-Text Card -->
              <div class="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-dark)]/30">
                <label class="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    bind:checked={whisperEnabled}
                    class="w-5 h-5 mt-0.5 accent-[var(--color-primary)] rounded"
                  />
                  <div class="flex-1">
                    <div class="flex items-center gap-2">
                      <Icon name="mic" size={18} class="text-[var(--color-primary)]" />
                      <span class="font-medium">Speech-to-Text</span>
                    </div>
                    <p class="text-xs text-[var(--color-text-muted)] mt-1">
                      Transcribe audio using WhisperLive AI
                    </p>
                  </div>
                </label>

                {#if whisperEnabled}
                  <div class="mt-4 pt-4 border-t border-[var(--color-border)] space-y-3">
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        bind:checked={saveTranscriptsToFile}
                        class="w-4 h-4 accent-[var(--color-primary)]"
                      />
                      <span class="text-sm">Save transcripts to file</span>
                    </label>

                    {#if saveTranscriptsToFile}
                      <div class="ml-7">
                        <input
                          type="text"
                          bind:value={transcriptFilePath}
                          placeholder="/data/transcripts/{name}.txt"
                          class="w-full px-3 py-2 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded-lg focus:border-[var(--color-primary)] focus:outline-none font-mono text-xs"
                        />
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>

              <!-- Face Detection Card -->
              <div class="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-dark)]/30">
                <label class="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    bind:checked={faceDetectionEnabled}
                    class="w-5 h-5 mt-0.5 accent-[var(--color-primary)] rounded"
                  />
                  <div class="flex-1">
                    <div class="flex items-center gap-2">
                      <Icon name="user" size={18} class="text-[var(--color-primary)]" />
                      <span class="font-medium">Face Detection</span>
                    </div>
                    <p class="text-xs text-[var(--color-text-muted)] mt-1">
                      Detect and identify faces using InsightFace
                    </p>
                  </div>
                </label>

                {#if faceDetectionEnabled}
                  <div class="mt-4 pt-4 border-t border-[var(--color-border)]">
                    <label for="face-interval" class="block text-sm mb-2">Detection Interval</label>
                    <div class="flex items-center gap-3">
                      <input
                        type="range"
                        id="face-interval"
                        min="0.5"
                        max="10"
                        step="0.5"
                        bind:value={faceDetectionInterval}
                        class="flex-1 h-2 bg-[var(--color-bg-hover)] rounded-lg appearance-none cursor-pointer accent-[var(--color-primary)]"
                      />
                      <span class="text-sm font-mono w-12 text-right">{faceDetectionInterval}s</span>
                    </div>
                    <p class="mt-2 text-xs text-[var(--color-text-muted)]">
                      Higher values reduce CPU usage
                    </p>
                  </div>
                {/if}
              </div>

              <!-- Recording Card -->
              <div class="p-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-dark)]/30">
                <label class="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    bind:checked={recordingEnabled}
                    class="w-5 h-5 mt-0.5 accent-[var(--color-primary)] rounded"
                  />
                  <div class="flex-1">
                    <div class="flex items-center gap-2">
                      <Icon name="video" size={18} class="text-[var(--color-primary)]" />
                      <span class="font-medium">24/7 Recording</span>
                    </div>
                    <p class="text-xs text-[var(--color-text-muted)] mt-1">
                      Continuous recording in 15-minute segments
                    </p>
                  </div>
                </label>

                {#if recordingEnabled}
                  <div class="mt-4 pt-4 border-t border-[var(--color-border)]">
                    <label for="retention-days" class="block text-sm mb-2">Retention Period</label>
                    <div class="flex items-center gap-3">
                      <input
                        type="range"
                        id="retention-days"
                        min="1"
                        max="30"
                        step="1"
                        bind:value={recordingRetentionDays}
                        class="flex-1 h-2 bg-[var(--color-bg-hover)] rounded-lg appearance-none cursor-pointer accent-[var(--color-primary)]"
                      />
                      <span class="text-sm font-mono w-16 text-right">{recordingRetentionDays} days</span>
                    </div>
                    <p class="mt-2 text-xs text-[var(--color-text-muted)]">
                      Recordings older than this will be automatically deleted
                    </p>
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <!-- Audio Tab -->
          {#if activeTab === 'audio'}
            <div class="space-y-5">
              {#if !whisperEnabled}
                <div class="p-4 bg-[var(--color-bg-dark)]/50 rounded-lg border border-[var(--color-border)] text-center">
                  <Icon name="volume" size={32} class="text-[var(--color-text-muted)] mx-auto mb-2" />
                  <p class="text-sm text-[var(--color-text-muted)]">
                    Enable Speech-to-Text in the Features tab to configure audio settings.
                  </p>
                </div>
              {:else}
                <!-- Audio Visualizer -->
                {#if isEditing && stream && status?.is_running}
                  <div class="p-4 bg-[var(--color-bg-dark)] rounded-lg border border-[var(--color-border)]">
                    <div class="flex items-center justify-between mb-3">
                      <span class="text-sm font-medium">Live Audio Levels</span>
                      <span class="text-xs text-[var(--color-success)] flex items-center gap-1">
                        <span class="w-2 h-2 bg-[var(--color-success)] rounded-full animate-pulse"></span>
                        Active
                      </span>
                    </div>
                    <AudioVisualizer
                      streamId={stream.id}
                      isRunning={true}
                      energyThreshold={audioEnergyThreshold ?? DEFAULTS.energy_threshold}
                      vadThreshold={audioVadThreshold ?? DEFAULTS.vad_threshold}
                    />
                  </div>
                {/if}

                <p class="text-xs text-[var(--color-text-muted)]">
                  Fine-tune audio filtering to reduce hallucinations. Leave at defaults unless experiencing issues.
                </p>

                <!-- Energy Threshold -->
                <div class="p-4 bg-[var(--color-bg-dark)]/30 rounded-lg border border-[var(--color-border)]">
                  <div class="flex items-center justify-between mb-3">
                    <label for="energy-threshold" class="text-sm font-medium">Energy Gate</label>
                    <span class="text-xs font-mono px-2 py-1 bg-[var(--color-bg-dark)] rounded {audioEnergyThreshold !== null ? 'text-[var(--color-primary)]' : 'text-[var(--color-text-muted)]'}">
                      {audioEnergyThreshold !== null ? audioEnergyThreshold.toFixed(3) : `${DEFAULTS.energy_threshold} (default)`}
                    </span>
                  </div>
                  <input
                    type="range"
                    id="energy-threshold"
                    min="0"
                    max="0.1"
                    step="0.005"
                    value={audioEnergyThreshold ?? DEFAULTS.energy_threshold}
                    oninput={(e) => audioEnergyThreshold = parseFloat(e.target.value)}
                    class="w-full h-2 bg-[var(--color-bg-hover)] rounded-lg appearance-none cursor-pointer accent-[var(--color-primary)]"
                  />
                  <p class="mt-2 text-xs text-[var(--color-text-muted)]">
                    Skip audio below this RMS level. Increase to filter more noise.
                  </p>
                </div>

                <!-- Silero VAD -->
                <div class="p-4 bg-[var(--color-bg-dark)]/30 rounded-lg border border-[var(--color-border)]">
                  <div class="flex items-center justify-between mb-3">
                    <label class="flex items-center gap-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={audioVadEnabled ?? DEFAULTS.vad_enabled}
                        onchange={(e) => audioVadEnabled = e.target.checked}
                        class="w-4 h-4 accent-[var(--color-primary)]"
                      />
                      <span class="text-sm font-medium">Silero VAD</span>
                    </label>
                    <span class="text-xs px-2 py-1 rounded {audioVadEnabled !== null ? 'bg-[var(--color-primary)]/20 text-[var(--color-primary)]' : 'bg-[var(--color-bg-dark)] text-[var(--color-text-muted)]'}">
                      {audioVadEnabled !== null ? (audioVadEnabled ? 'Custom: On' : 'Custom: Off') : 'Default'}
                    </span>
                  </div>
                  <p class="text-xs text-[var(--color-text-muted)]">
                    Neural network-based voice activity detection for accurate speech filtering.
                  </p>
                </div>

                <!-- VAD Threshold -->
                <div class="p-4 bg-[var(--color-bg-dark)]/30 rounded-lg border border-[var(--color-border)]">
                  <div class="flex items-center justify-between mb-3">
                    <label for="vad-threshold" class="text-sm font-medium">VAD Threshold</label>
                    <span class="text-xs font-mono px-2 py-1 bg-[var(--color-bg-dark)] rounded {audioVadThreshold !== null ? 'text-[var(--color-primary)]' : 'text-[var(--color-text-muted)]'}">
                      {audioVadThreshold !== null ? audioVadThreshold.toFixed(2) : `${DEFAULTS.vad_threshold} (default)`}
                    </span>
                  </div>
                  <input
                    type="range"
                    id="vad-threshold"
                    min="0.1"
                    max="0.95"
                    step="0.05"
                    value={audioVadThreshold ?? DEFAULTS.vad_threshold}
                    oninput={(e) => audioVadThreshold = parseFloat(e.target.value)}
                    class="w-full h-2 bg-[var(--color-bg-hover)] rounded-lg appearance-none cursor-pointer accent-[var(--color-primary)]"
                  />
                  <p class="mt-2 text-xs text-[var(--color-text-muted)]">
                    Speech probability threshold. Higher = stricter, may miss quiet speech.
                  </p>
                </div>

                <!-- Advanced: VAD Onset/Offset -->
                <details class="group">
                  <summary class="flex items-center gap-2 text-sm font-medium text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-text)] transition-colors">
                    <Icon name="chevron-right" size={16} class="group-open:rotate-90 transition-transform" />
                    Advanced VAD Settings
                  </summary>
                  <div class="mt-3 grid grid-cols-2 gap-3">
                    <div class="p-3 bg-[var(--color-bg-dark)]/30 rounded-lg border border-[var(--color-border)]">
                      <label for="vad-onset" class="block text-xs font-medium mb-2">VAD Onset</label>
                      <input
                        type="number"
                        id="vad-onset"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        value={audioVadOnset ?? DEFAULTS.vad_onset}
                        oninput={(e) => audioVadOnset = parseFloat(e.target.value) || null}
                        class="w-full px-3 py-2 text-sm bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded-lg"
                      />
                    </div>
                    <div class="p-3 bg-[var(--color-bg-dark)]/30 rounded-lg border border-[var(--color-border)]">
                      <label for="vad-offset" class="block text-xs font-medium mb-2">VAD Offset</label>
                      <input
                        type="number"
                        id="vad-offset"
                        min="0.1"
                        max="0.9"
                        step="0.05"
                        value={audioVadOffset ?? DEFAULTS.vad_offset}
                        oninput={(e) => audioVadOffset = parseFloat(e.target.value) || null}
                        class="w-full px-3 py-2 text-sm bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded-lg"
                      />
                    </div>
                  </div>
                </details>

                <!-- Audio Preview & Reset -->
                <div class="flex items-center justify-between pt-4 border-t border-[var(--color-border)]">
                  {#if isEditing && stream}
                    <AudioPreview streamId={stream.id} isRunning={status?.is_running ?? false} />
                  {:else}
                    <span class="text-xs text-[var(--color-text-muted)]">Save stream to preview audio</span>
                  {/if}
                  <button
                    type="button"
                    onclick={resetAudioToDefaults}
                    disabled={!hasCustomAudio}
                    class="text-xs px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                      {hasCustomAudio ? 'text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10' : 'text-[var(--color-text-muted)]'}"
                  >
                    Reset to Defaults
                  </button>
                </div>
              {/if}
            </div>
          {/if}
        </div>

        <!-- Footer (sticky) -->
        <div class="flex-shrink-0 flex items-center justify-between px-6 py-4 border-t border-[var(--color-border)] bg-[var(--color-bg-card)]">
          {#if isEditing}
            <button
              type="button"
              onclick={handleDelete}
              disabled={isLoading}
              class="flex items-center gap-2 px-4 py-2 text-sm font-medium text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10 rounded-lg transition-colors disabled:opacity-50"
            >
              <Icon name="trash" size={16} />
              Delete
            </button>
          {:else}
            <div></div>
          {/if}

          <div class="flex gap-3">
            <button
              type="button"
              onclick={onClose}
              class="px-4 py-2 text-sm font-medium text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              class="flex items-center gap-2 px-5 py-2 text-sm font-medium bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {#if isLoading}
                <Icon name="refresh" size={16} class="animate-spin" />
              {:else}
                <Icon name="check" size={16} />
              {/if}
              {isEditing ? 'Save Changes' : 'Create Stream'}
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
{/if}
