<script>
  import { onMount, onDestroy } from 'svelte';
  import { API_BASE } from '../services/api.js';

  let {
    streamId,
    energyThreshold = 0.015,
    vadThreshold = 0.6,
    isRunning = false
  } = $props();

  let canvas;
  let ctx;
  let ws = null;
  let animationFrame;
  let history = []; // Array of {rms, speech_prob, skipped_energy, skipped_vad}
  const HISTORY_SIZE = 100; // Number of data points to show

  // Colors
  const COLOR_BG = '#1a1a1a';
  const COLOR_GRID = '#333';
  const COLOR_RMS_OK = '#22c55e'; // Green
  const COLOR_RMS_LOW = '#ef4444'; // Red (skipped)
  const COLOR_VAD = '#3b82f6'; // Blue
  const COLOR_THRESH_RMS = '#eab308'; // Yellow
  const COLOR_THRESH_VAD = '#a855f7'; // Purple

  function connect() {
    if (ws) return;
    if (!streamId || !isRunning) return;

    // Use ws:// or wss:// based on current protocol
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}${API_BASE}/streams/${streamId}/audio-levels`;

    ws = new WebSocket(url);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        history.push(data);
        if (history.length > HISTORY_SIZE) {
          history.shift();
        }
      } catch (e) {
        console.error('Failed to parse audio levels:', e);
      }
    };

    ws.onclose = () => {
      ws = null;
      // Try reconnect if still running
      if (isRunning) {
        setTimeout(connect, 2000);
      }
    };
  }

  function disconnect() {
    if (ws) {
      ws.close();
      ws = null;
    }
  }

  function draw() {
    if (!ctx || !canvas) return;

    const width = canvas.width;
    const height = canvas.height;
    
    // Clear
    ctx.fillStyle = COLOR_BG;
    ctx.fillRect(0, 0, width, height);

    // Grid lines
    ctx.strokeStyle = COLOR_GRID;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();

    if (history.length === 0) {
      animationFrame = requestAnimationFrame(draw);
      return;
    }

    const barWidth = width / HISTORY_SIZE;
    
    // Draw RMS bars (bottom up)
    // Scale RMS: 0.0 to 0.1 (common range for this application) usually fills the graph
    // We'll scale so 0.1 is 80% height
    const rmsScale = height * 8; 

    history.forEach((point, i) => {
      const x = i * barWidth;
      
      // RMS Bar
      const rmsHeight = Math.min(point.rms * rmsScale, height);
      ctx.fillStyle = point.skipped_energy ? COLOR_RMS_LOW : COLOR_RMS_OK;
      ctx.fillRect(x, height - rmsHeight, barWidth - 1, rmsHeight);
      
      // VAD Line (overlay)
      // VAD is 0.0 to 1.0, map to height
      const vadY = height - (point.speech_prob * height);
      ctx.fillStyle = COLOR_VAD;
      ctx.fillRect(x, vadY, barWidth, 2);
    });

    // Draw Threshold Lines
    
    // Energy Threshold
    const threshY = height - Math.min(energyThreshold * rmsScale, height);
    ctx.strokeStyle = COLOR_THRESH_RMS;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(0, threshY);
    ctx.lineTo(width, threshY);
    ctx.stroke();
    
    // VAD Threshold
    const vadThreshY = height - (vadThreshold * height);
    ctx.strokeStyle = COLOR_THRESH_VAD;
    ctx.beginPath();
    ctx.moveTo(0, vadThreshY);
    ctx.lineTo(width, vadThreshY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Legend text
    ctx.fillStyle = COLOR_THRESH_RMS;
    ctx.font = '10px monospace';
    ctx.fillText(`Energy Thresh: ${energyThreshold}`, 5, threshY - 5);

    ctx.fillStyle = COLOR_THRESH_VAD;
    ctx.fillText(`VAD Thresh: ${vadThreshold}`, 5, vadThreshY - 5);

    animationFrame = requestAnimationFrame(draw);
  }

  $effect(() => {
    if (isRunning) {
      connect();
      if (!animationFrame) draw();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
      if (animationFrame) cancelAnimationFrame(animationFrame);
    };
  });

  onMount(() => {
    ctx = canvas.getContext('2d');
    draw();
  });
</script>

<div class="audio-visualizer bg-[var(--color-bg-dark)] border border-[var(--color-border)] rounded overflow-hidden">
  <canvas
    bind:this={canvas}
    width="400"
    height="150"
    class="w-full h-full block"
  ></canvas>
  <div class="flex justify-between px-2 py-1 text-[10px] text-[var(--color-text-muted)] bg-[var(--color-bg-card)]">
    <div class="flex gap-2">
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-green-500"></span> Audio OK</span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500"></span> Silence (Energy)</span>
    </div>
    <div class="flex gap-2">
      <span class="flex items-center gap-1"><span class="w-2 h-2 bg-blue-500"></span> VAD Prob</span>
      <span class="flex items-center gap-1"><span class="w-2 h-2 bg-purple-500"></span> VAD Thresh</span>
    </div>
  </div>
</div>
