<template>
  <span class="run-status" :data-status="status">
    <span class="status-mark" aria-hidden="true"></span>
    {{ te('runTrace.states.' + status) ? t('runTrace.states.' + status) : status }}
  </span>
</template>
<script setup lang="ts">
import { useI18n } from 'vue-i18n'
defineProps<{ status: string }>()
const { te, t } = useI18n({ useScope: 'global' })
</script>
<style scoped>
.run-status {
  --tone: #4b5861;
  --tint: #edf0f2;
  display: inline-flex;
  gap: 6px;
  align-items: center;
  flex: none;
  width: max-content;
  max-width: 100%;
  padding: 3px 9px;
  line-height: 1.5;
  color: var(--tone);
  background: var(--tint);
  border-radius: 99px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}
.status-mark {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}
[data-status='succeeded'] {
  --tone: #216344;
  --tint: var(--studio-selection);
}
[data-status='running'] {
  --tone: var(--studio-ink);
  --tint: #e0f0f1;
}
[data-status='waiting_input'] {
  --tone: #82530d;
  --tint: #fff1d8;
}
[data-status='failed'] {
  --tone: #a03837;
  --tint: #fbe9e7;
}
[data-status='cancelled'] .status-mark {
  border-radius: 1px;
}
[data-status='queued'] .status-mark {
  background: transparent;
  box-shadow: inset 0 0 0 1.5px currentColor;
}
</style>
