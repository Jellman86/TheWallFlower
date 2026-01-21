<script>
  let {
    faces = [],
    containerWidth = 0,
    containerHeight = 0,
    videoWidth = 0,
    videoHeight = 0,
    showUnknown = true
  } = $props();

  function getDisplayMetrics() {
    if (!containerWidth || !containerHeight || !videoWidth || !videoHeight) {
      return null;
    }
    const scale = Math.min(containerWidth / videoWidth, containerHeight / videoHeight);
    const displayWidth = videoWidth * scale;
    const displayHeight = videoHeight * scale;
    const offsetX = (containerWidth - displayWidth) / 2;
    const offsetY = (containerHeight - displayHeight) / 2;
    return { displayWidth, displayHeight, offsetX, offsetY };
  }

  let metrics = $derived(getDisplayMetrics());

  function boxStyle(face) {
    if (!metrics || !face?.frame_width || !face?.frame_height) return '';
    const boxWidth = (face.bbox_x2 - face.bbox_x1) / face.frame_width * metrics.displayWidth;
    const boxHeight = (face.bbox_y2 - face.bbox_y1) / face.frame_height * metrics.displayHeight;
    const left = metrics.offsetX + (face.bbox_x1 / face.frame_width) * metrics.displayWidth;
    const top = metrics.offsetY + (face.bbox_y1 / face.frame_height) * metrics.displayHeight;
    return `left:${left}px;top:${top}px;width:${boxWidth}px;height:${boxHeight}px;`;
  }
</script>

{#if metrics}
  <div class="absolute inset-0 pointer-events-none">
    {#each faces as face (face.id)}
      {#if face.frame_width && face.frame_height}
        {#if showUnknown || (face.face_name && !face.face_name.startsWith('Unknown'))}
          <div
            class="absolute border-2 border-[var(--color-primary)] bg-black/20 text-[10px] text-white px-1 py-0.5 rounded"
            style={boxStyle(face)}
          >
            <div class="absolute -top-5 left-0 bg-black/70 px-1 rounded">
              {face.face_name || 'Unknown'}
            </div>
          </div>
        {/if}
      {/if}
    {/each}
  </div>
{/if}
