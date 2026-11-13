<template>
  <span class="wordmark" :title="branding.name" :style="{ fontSize: height }">
    <LogoIcon height="1em" />
    <span>{{ branding.name }}</span>
  </span>
</template>
<script setup lang="ts">
import { branding } from '@/utils/branding'
import LogoIcon from './LogoIcon.vue'
defineOptions({ name: 'LogoFull' })
withDefaults(defineProps<{ height?: string }>(), { height: '29px' })
</script>
<style scoped>
.wordmark {
  display: inline-flex;
  align-items: center;
  gap: 0.29em;
  max-width: min(11em, 100%);
  vertical-align: middle;
}
.wordmark span {
  color: var(--studio-ink);
  font-size: 0.84em;
  font-weight: 700;
  letter-spacing: -0.035em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
