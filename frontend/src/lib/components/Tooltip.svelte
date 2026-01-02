<script>
  let { text = '', position = 'top' } = $props();
</script>

<div class="tooltip-wrapper group relative inline-flex items-center">
  <slot />
  <div class="tooltip opacity-0 invisible group-hover:opacity-100 group-hover:visible
    absolute z-50 px-3 py-2 text-xs font-normal text-white bg-gray-900 rounded-lg shadow-lg
    transition-opacity duration-200 whitespace-normal max-w-xs
    {position === 'top' ? 'bottom-full left-1/2 -translate-x-1/2 mb-2' : ''}
    {position === 'bottom' ? 'top-full left-1/2 -translate-x-1/2 mt-2' : ''}
    {position === 'left' ? 'right-full top-1/2 -translate-y-1/2 mr-2' : ''}
    {position === 'right' ? 'left-full top-1/2 -translate-y-1/2 ml-2' : ''}">
    {text}
    <!-- Arrow -->
    <div class="absolute w-2 h-2 bg-gray-900 rotate-45
      {position === 'top' ? 'top-full left-1/2 -translate-x-1/2 -mt-1' : ''}
      {position === 'bottom' ? 'bottom-full left-1/2 -translate-x-1/2 -mb-1' : ''}
      {position === 'left' ? 'left-full top-1/2 -translate-y-1/2 -ml-1' : ''}
      {position === 'right' ? 'right-full top-1/2 -translate-y-1/2 -mr-1' : ''}">
    </div>
  </div>
</div>

<style>
  .tooltip-wrapper:hover .tooltip {
    opacity: 1;
    visibility: visible;
  }
</style>
