<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { loadBranding } from '@/utils/branding'

void loadBranding().catch(() => {})
const route = useRoute()
const viewport = ref<HTMLElement>()
let entrance: Animation | undefined

watch(() => route.path, () => {
  entrance?.cancel()
  const root = viewport.value
  if (!root || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const content = root.querySelector<HTMLElement>('.settings-content') ||
    root.querySelector<HTMLElement>('.studio-main-content')
  // Keep the shell fixed. Full-screen editors also keep their canvas coordinates during navigation.
  const frames = content
    ? [{ opacity: 0.65, transform: 'translateY(4px)' }, { opacity: 1, transform: 'translateY(0)' }]
    : [{ opacity: 0.72 }, { opacity: 1 }]
  entrance = (content || root).animate(frames, { duration: 180, easing: 'cubic-bezier(.2,.72,.25,1)' })
}, { flush: 'post' })
onBeforeUnmount(() => entrance?.cancel())
</script>
<template>
  <div ref="viewport" class="studio-viewport"><RouterView /></div>
</template>
<style scoped>
.studio-viewport { height: 100%; min-width: 0; }
</style>
