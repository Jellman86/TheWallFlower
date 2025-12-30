<script>
  import { onMount, onDestroy } from 'svelte';
  import { go2rtc } from '../services/api.js';
  import Icon from './Icons.svelte';

  let { 
    streamId, 
    muted = true,
    poster = '',
    onStatusChange = () => {} 
  } = $props();

  let videoElement;
  let pc = null;
  let error = $state(null);
  let connectionState = $state('new'); // new, checking, connected, disconnected, failed, closed
  let isReconnecting = $state(false);
  let retryCount = 0;
  const MAX_RETRIES = 5;
  let retryTimeout = null;

  // Configuration for RTCPeerConnection
  // We rely on go2rtc to handle ICE gathering mostly, but stuns can help
  const rtcConfig = {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' }
    ],
    sdpSemantics: 'unified-plan'
  };

  onMount(() => {
    startWebRTC();
  });

  onDestroy(() => {
    cleanup();
  });

  function cleanup() {
    if (retryTimeout) clearTimeout(retryTimeout);
    
    if (pc) {
      // Close all transceivers
      pc.getTransceivers().forEach(t => {
        if (t.stop) t.stop();
      });
      pc.close();
      pc = null;
    }
    
    if (videoElement) {
      videoElement.srcObject = null;
    }
  }

  async function startWebRTC() {
    cleanup();
    error = null;
    connectionState = 'checking';
    onStatusChange('connecting');

    try {
      pc = new RTCPeerConnection(rtcConfig);

      // Connection state handling
      pc.onconnectionstatechange = () => {
        connectionState = pc.connectionState;
        console.log(`[WebRTC ${streamId}] Connection state:`, connectionState);
        
        if (connectionState === 'connected') {
          onStatusChange('connected');
          retryCount = 0;
          isReconnecting = false;
        } else if (connectionState === 'failed' || connectionState === 'disconnected') {
          onStatusChange('error');
          handleRetry();
        }
      };

      // Handle incoming tracks
      pc.ontrack = (event) => {
        console.log(`[WebRTC ${streamId}] Received track:`, event.track.kind);
        if (videoElement && event.streams[0]) {
          videoElement.srcObject = event.streams[0];
          // Ensure playback starts
          videoElement.play().catch(e => {
            // Autoplay might be blocked if not muted
            if (e.name === 'NotAllowedError' && !muted) {
              console.warn('Autoplay blocked, muting and retrying');
              muted = true;
              videoElement.muted = true;
              videoElement.play().catch(console.error);
            }
          });
        }
      };

      // Add transceivers (we want to receive video and audio)
      // 'recvonly' tells the server we only want to receive media
      pc.addTransceiver('video', { direction: 'recvonly' });
      pc.addTransceiver('audio', { direction: 'recvonly' });

      // Create offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // Wait for ICE gathering to complete (or timeout)
      // This ensures the SDP we send contains the necessary candidates
      // Crucial for connectivity when not on localhost
      await new Promise(resolve => {
        if (pc.iceGatheringState === 'complete') {
          resolve();
          return;
        }
        
        const checkState = () => {
          if (pc.iceGatheringState === 'complete') {
            pc.removeEventListener('icegatheringstatechange', checkState);
            resolve();
          }
        };
        
        pc.addEventListener('icegatheringstatechange', checkState);
        
        // Wait max 1s for candidates - usually sufficient for local/LAN
        // If gathering takes longer, we'll send what we have
        setTimeout(() => {
            pc.removeEventListener('icegatheringstatechange', checkState);
            resolve();
        }, 1000);
      });

      // Send to backend
      const response = await fetch(go2rtc.webrtcApiUrl(streamId), {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: pc.localDescription.sdp // Use localDescription to include candidates
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const answerSdp = await response.text();
      // Handle the case where the server returns an empty body or error text
      if (!answerSdp || !answerSdp.includes('m=video')) {
         // Try to parse as JSON just in case it's an error object
         try {
           const errJson = JSON.parse(answerSdp);
           throw new Error(errJson.detail || 'Invalid SDP answer');
         } catch (e) {
           if (e.message.includes('Invalid SDP')) throw e;
           throw new Error('Invalid SDP response from server');
         }
      }

      await pc.setRemoteDescription(new RTCSessionDescription({
        type: 'answer',
        sdp: answerSdp
      }));

    } catch (e) {
      console.error(`[WebRTC ${streamId}] Error:`, e);
      error = e.message;
      connectionState = 'failed';
      onStatusChange('error');
      handleRetry();
    }
  }

  function handleRetry() {
    if (retryCount >= MAX_RETRIES) {
      error = "Connection failed after multiple attempts";
      return;
    }

    retryCount++;
    isReconnecting = true;
    const delay = Math.min(2000 * Math.pow(2, retryCount - 1), 30000);
    console.log(`[WebRTC ${streamId}] Retrying in ${delay}ms...`);
    
    if (retryTimeout) clearTimeout(retryTimeout);
    retryTimeout = setTimeout(() => {
      startWebRTC();
    }, delay);
  }
</script>

<div class="relative w-full h-full bg-black flex items-center justify-center overflow-hidden">
  <video
    bind:this={videoElement}
    autoplay
    playsinline
    {muted}
    {poster}
    class="w-full h-full object-contain"
    controls={false}
  ></video>

  <!-- Overlay Statuses -->
  {#if connectionState === 'new' || connectionState === 'checking'}
    <div class="absolute inset-0 flex items-center justify-center bg-black/50 z-10 pointer-events-none">
      <div class="flex flex-col items-center text-[var(--color-text-muted)]">
        <Icon name="loader" size={32} class="animate-spin mb-2" />
        <span class="text-xs">Connecting...</span>
      </div>
    </div>
  {:else if connectionState === 'disconnected' || isReconnecting}
    <div class="absolute inset-0 flex items-center justify-center bg-black/50 z-10 pointer-events-none">
      <div class="flex flex-col items-center text-[var(--color-warning)]">
        <Icon name="rotate" size={32} class="animate-spin mb-2" />
        <span class="text-xs">Reconnecting...</span>
      </div>
    </div>
  {:else if error || connectionState === 'failed'}
    <div class="absolute inset-0 flex items-center justify-center bg-black/80 z-10">
      <div class="flex flex-col items-center text-[var(--color-danger)] p-4 text-center">
        <Icon name="x" size={32} class="mb-2" />
        <span class="text-sm font-medium">Stream Failed</span>
        <span class="text-xs mt-1 text-[var(--color-text-muted)]">{error || 'Unknown error'}</span>
        <button 
          onclick={() => { retryCount = 0; startWebRTC(); }}
          class="mt-4 px-3 py-1 bg-[var(--color-bg-light)] hover:bg-[var(--color-bg-hover)] rounded text-xs text-[var(--color-text)] transition-colors"
        >
          Retry
        </button>
      </div>
    </div>
  {/if}

  <!-- Unmute Button (if sound is available but muted) -->
  <div class="absolute bottom-2 right-2 z-20 opacity-0 hover:opacity-100 transition-opacity">
    <button
      onclick={() => muted = !muted}
      class="p-2 bg-black/50 hover:bg-black/70 rounded-full text-white backdrop-blur-sm"
      title={muted ? "Unmute" : "Mute"}
    >
      <Icon name={muted ? "volume-x" : "volume"} size={18} />
    </button>
  </div>
</div>