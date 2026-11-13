<template>
  <div class="list-placeholder" role="status" :aria-label="$t('components.loading')">
    <div v-for="n in 3" :key="n" class="placeholder-card" aria-hidden="true">
      <i></i><span></span><span></span>
    </div>
  </div>
</template>
<style scoped>
.list-placeholder {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 270px), 1fr)); gap: 14px;
  /* Quick responses keep their layout space without flashing a loading indicator. */
  animation: placeholder-in 160ms ease-out 100ms backwards;
}
.placeholder-card {
  display: grid; align-content: center; gap: 12px; min-height: 112px; padding: 16px;
  box-sizing: border-box; border: 1px solid var(--studio-hairline);
  border-radius: var(--app-border-radius-large); background: var(--el-bg-color);
}
.placeholder-card > * {
  display: block; background: var(--el-fill-color); border-radius: 4px;
}
.placeholder-card i { width: 28px; height: 28px; border-radius: 8px; }
.placeholder-card span { width: 56%; height: 9px; }
.placeholder-card span:last-child { width: 78%; }
@keyframes placeholder-in { from { opacity: 0; } to { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .list-placeholder { animation: none; } }
</style>
