<script setup lang="ts">
import { pendingRoute } from '@/router'
import { loadBranding } from '@/utils/branding'

void loadBranding().catch(() => {})
</script>
<template>
  <div class="studio-viewport">
    <div v-if="pendingRoute" class="route-progress" aria-hidden="true"></div>
    <div class="route-page"><RouterView /></div>
  </div>
</template>
<style scoped>
.studio-viewport, .route-page { height: 100%; min-width: 0; }
.studio-viewport { overflow-x: clip; }
.route-progress {
  position: fixed; inset: 0 0 auto; height: 2px; z-index: 4000; pointer-events: none;
  background: var(--studio-ink); transform-origin: left; opacity: 0;
  animation: route-wait 1.6s cubic-bezier(.12,.65,.24,1) 100ms forwards;
}
@keyframes route-wait {
  from { opacity: 0; transform: scaleX(.1); }
  12% { opacity: .85; }
  to { opacity: .85; transform: scaleX(.9); }
}
@media (prefers-reduced-motion: reduce) {
  .route-progress { animation: none; transform: scaleX(.25); opacity: 1; }
}
</style>
