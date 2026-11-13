<template>
  <header class="workspace-bar">
    <RouterLink class="workspace-brand" to="/" :aria-label="branding.name">
      <LogoFull height="32px" />
    </RouterLink>
    <TopMenu class="workspace-nav" />
    <div class="account"><Avatar /></div>
  </header>
</template>
<script setup lang="ts">
import TopMenu from './top-menu/index.vue'
import Avatar from './avatar/index.vue'
import { branding } from '@/utils/branding'
</script>
<style lang="scss" scoped>
.workspace-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(40px, 1fr);
  align-items: center;
  gap: 16px;
  height: var(--app-header-height);
  box-sizing: border-box;
  padding: var(--app-header-padding);
}
.workspace-brand {
  min-width: 0;
  width: fit-content;
  max-width: 100%;
  border-radius: 8px;
}
.account {
  justify-self: end;
}
@media (max-width: 820px) {
  .workspace-bar {
    grid-template-columns: minmax(0, 1fr) auto;
    grid-template-rows: 45px 44px;
    padding: 3px 14px 8px;
    gap: 4px 8px;
  }
  .workspace-brand {
    grid-area: 1 / 1;
  }
  .account {
    grid-area: 1 / 2;
  }
  .workspace-nav {
    grid-area: 2 / 1 / 3 / -1;
    max-width: 100%;
    justify-self: start;
  }
}
</style>
