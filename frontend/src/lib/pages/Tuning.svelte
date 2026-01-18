<script>
  import { onMount } from 'svelte';
  import Icon from '../components/Icons.svelte';
  
  // API base URL
  const API_BASE = '/api/tuning';

  let samples = $state([]);
  let selectedSample = $state(null);
  let tuningRuns = $state([]);
  let isLoading = $state(false);
  let isTuning = $state(false);
  
  // New sample form
  let fileInput;
  let isUploading = $state(false);

  onMount(() => {
    loadSamples();
  });

  async function loadSamples() {
    isLoading = true;
    try {
      const res = await fetch(`${API_BASE}/samples`);
      if (res.ok) {
        samples = await res.json();
      }
    } catch (e) {
      console.error(e);
    }
    isLoading = false;
  }

  async function handleUpload() {
    if (!fileInput.files[0]) return;
    
    isUploading = true;
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    
    try {
      const res = await fetch(`${API_BASE}/samples`, {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        const newSample = await res.json();
        samples = [newSample, ...samples];
        fileInput.value = ''; // Reset
        selectSample(newSample);
      } else {
        alert('Upload failed');
      }
    } catch (e) {
      alert('Upload failed: ' + e.message);
    }
    isUploading = false;
  }

  async function selectSample(sample) {
    selectedSample = sample;
    await loadRuns(sample.id);
  }

  async function loadRuns(sampleId) {
    try {
        const res = await fetch(`${API_BASE}/samples/${sampleId}/runs`);
        if (res.ok) {
            tuningRuns = await res.json();
        }
    } catch (e) {
        console.error(e);
    }
  }

  async function handleSaveGT() {
    if (!selectedSample) return;
    try {
        const res = await fetch(`${API_BASE}/samples/${selectedSample.id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ground_truth: selectedSample.ground_truth})
        });
        if (res.ok) {
            alert('Saved');
        } else {
            alert('Save failed');
        }
    } catch(e) {
        alert('Save failed');
    }
  }

  async function handleTune() {
    if (!selectedSample) return;
    isTuning = true;
    try {
        const res = await fetch(`${API_BASE}/samples/${selectedSample.id}/tune`, { method: 'POST' });
        if (res.ok) {
            // Simple polling for demo purposes
            setTimeout(() => loadRuns(selectedSample.id), 2000);
            setTimeout(() => loadRuns(selectedSample.id), 5000);
            setTimeout(() => loadRuns(selectedSample.id), 10000);
            setTimeout(() => loadRuns(selectedSample.id), 20000); // Longer wait for full sweep
        } else {
            alert('Tuning failed to start');
        }
    } catch(e) {
        alert('Tuning start failed');
    }
    isTuning = false;
  }
  
  async function handleDelete(e, id) {
    e.stopPropagation();
    if(!confirm('Delete this sample?')) return;
    
    try {
        await fetch(`${API_BASE}/samples/${id}`, { method: 'DELETE' });
        if (selectedSample && selectedSample.id === id) selectedSample = null;
        loadSamples();
    } catch (e) {
        console.error(e);
    }
  }
</script>

<div class="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[calc(100vh-140px)]">
  <!-- Sidebar: Sample List -->
  <div class="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg flex flex-col overflow-hidden">
    <div class="p-4 border-b border-[var(--color-border)]">
      <h3 class="font-bold mb-2">Audio Samples</h3>
      <div class="flex gap-2">
        <input 
            type="file" 
            accept=".wav" 
            bind:this={fileInput}
            class="hidden" 
            onchange={handleUpload}
        />
        <button 
            onclick={() => fileInput.click()}
            disabled={isUploading}
            class="w-full py-2 bg-[var(--color-primary)] text-white rounded text-sm hover:bg-[var(--color-primary-dark)] flex items-center justify-center gap-2"
        >
            <Icon name={isUploading ? 'refresh' : 'plus'} size={16} class={isUploading ? 'animate-spin' : ''} />
            {isUploading ? 'Uploading...' : 'Upload .wav'}
        </button>
      </div>
      <p class="text-xs text-[var(--color-text-muted)] mt-2">
        Required: 16kHz Mono WAV (Float32 or PCM16)
      </p>
    </div>
    
    <div class="flex-1 overflow-y-auto p-2 space-y-2">
      {#each samples as sample (sample.id)}
        <button 
            onclick={() => selectSample(sample)}
            class="w-full text-left p-3 rounded hover:bg-[var(--color-bg-hover)] transition-colors border border-transparent
                   {selectedSample?.id === sample.id ? 'bg-[var(--color-bg-hover)] border-[var(--color-primary)]' : ''}"
        >
            <div class="flex justify-between items-start">
                <span class="font-medium truncate block w-full pr-6">{sample.filename}</span>
                <button onclick={(e) => handleDelete(e, sample.id)} class="text-[var(--color-text-muted)] hover:text-[var(--color-danger)]">
                    <Icon name="trash" size={14} />
                </button>
            </div>
            <div class="text-xs text-[var(--color-text-muted)] mt-1">
                {new Date(sample.created_at).toLocaleDateString()}
            </div>
        </button>
      {/each}
      
      {#if samples.length === 0 && !isLoading}
        <div class="text-center p-4 text-[var(--color-text-muted)] text-sm">
            No samples yet.
        </div>
      {/if}
    </div>
  </div>

  <!-- Main Area: Tuning -->
  <div class="lg:col-span-2 flex flex-col gap-6 overflow-y-auto">
    {#if selectedSample}
        <!-- Ground Truth Editor -->
        <div class="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg p-6 flex-shrink-0">
            <h3 class="font-bold mb-4 flex items-center gap-2">
                <Icon name="check" size={20} class="text-[var(--color-success)]"/>
                Ground Truth
            </h3>
            <p class="text-sm text-[var(--color-text-muted)] mb-2">
                Enter the exact expected text for this audio clip.
            </p>
            <textarea 
                bind:value={selectedSample.ground_truth}
                class="w-full h-24 bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded p-3 text-sm focus:border-[var(--color-primary)] outline-none resize-none"
                placeholder="Type the correct transcription here..."
            ></textarea>
            <div class="flex justify-end mt-3 gap-2">
                <button 
                    onclick={handleSaveGT}
                    class="px-4 py-2 bg-[var(--color-bg-hover)] rounded text-sm hover:bg-[var(--color-bg-dark)]"
                >
                    Save Text
                </button>
                <button 
                    onclick={handleTune}
                    disabled={!selectedSample.ground_truth || isTuning}
                    class="px-4 py-2 bg-[var(--color-primary)] text-white rounded text-sm hover:bg-[var(--color-primary-dark)] flex items-center gap-2 disabled:opacity-50"
                >
                    {#if isTuning}
                        <Icon name="refresh" size={16} class="animate-spin" /> Tuning...
                    {:else}
                        <Icon name="sliders" size={16} /> Run Auto-Tuner
                    {/if}
                </button>
            </div>
        </div>

        <!-- Results Leaderboard -->
        <div class="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg flex-1 overflow-hidden flex flex-col min-h-[300px]">
            <div class="p-4 border-b border-[var(--color-border)]">
                <h3 class="font-bold">Tuning Results (Lower WER is better)</h3>
            </div>
            <div class="overflow-x-auto flex-1">
                <table class="w-full text-sm text-left">
                    <thead class="bg-[var(--color-bg-dark)] text-[var(--color-text-muted)] sticky top-0">
                        <tr>
                            <th class="p-3">WER</th>
                            <th class="p-3">Beam</th>
                            <th class="p-3">Temp</th>
                            <th class="p-3">VAD</th>
                            <th class="p-3">Time</th>
                            <th class="p-3">Transcript</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-[var(--color-border)]">
                        {#each tuningRuns as run}
                            <tr class="hover:bg-[var(--color-bg-hover)]">
                                <td class="p-3 font-mono font-bold {run.wer === 0 ? 'text-[var(--color-success)]' : ''}">
                                    {(run.wer * 100).toFixed(1)}%
                                </td>
                                <td class="p-3">{run.beam_size}</td>
                                <td class="p-3 truncate max-w-[100px]" title={run.temperature}>
                                    {typeof run.temperature === 'string' && run.temperature.includes('[') ? 'Dynamic' : run.temperature}
                                </td>
                                <td class="p-3">{run.vad_threshold}</td>
                                <td class="p-3">{(run.execution_time).toFixed(2)}s</td>
                                <td class="p-3 text-[var(--color-text-muted)] truncate max-w-[200px]" title={run.transcription}>
                                    {run.transcription}
                                </td>
                            </tr>
                        {/each}
                        {#if tuningRuns.length === 0}
                            <tr>
                                <td colspan="6" class="p-8 text-center text-[var(--color-text-muted)]">
                                    No runs yet. Click "Run Auto-Tuner" to start.
                                </td>
                            </tr>
                        {/if}
                    </tbody>
                </table>
            </div>
        </div>
    {:else}
        <div class="h-full flex items-center justify-center text-[var(--color-text-muted)] bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-lg">
            <div class="text-center">
                <Icon name="mic" size={48} class="mx-auto mb-4 opacity-50" />
                <p>Select or upload a sample to start tuning.</p>
            </div>
        </div>
    {/if}
  </div>
</div>
