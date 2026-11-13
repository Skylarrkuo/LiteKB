<template>
  <router-link
    class="menu-item-container"
    :class="{ active: isActive, pending: pendingRoute?.meta.activeMenu === menu.path }"
    @pointerenter="schedulePreload" @pointerleave="cancelPreload"
    @focus="schedulePreload" @blur="cancelPreload"
    :to="{ name: menu.name }"
    :title="$t(menu.meta?.title as string)"
    :aria-label="$t(menu.meta?.title as string)"
    :aria-current="isActive ? 'page' : undefined"
  >
    <span class="menu-icon" aria-hidden="true">
      <AppIcon :iconName="isActive ? menu.meta?.iconActive || menu.meta?.icon : menu.meta?.icon" />
    </span>
    <span>{{ $t(menu.meta?.title as string) }}</span>
  </router-link>
</template>
<script setup lang="ts">
import { loadRouteLocation, useRouter, useRoute, type RouteRecordRaw } from 'vue-router'
import { computed, onBeforeUnmount } from 'vue'
import { pendingRoute } from '@/router'

const route = useRoute()

const props = defineProps<{
  menu: RouteRecordRaw
}>()

const router = useRouter()
let timer: number | undefined
function cancelPreload() {
  window.clearTimeout(timer)
}
function schedulePreload() {
  cancelPreload()
  if (isActive.value || (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData) return
  timer = window.setTimeout(() => {
    const target = router.resolve(props.menu.path)
    const redirect = target.matched[target.matched.length - 1]?.redirect
    const destination = redirect ? router.resolve(typeof redirect === 'function' ? redirect(target, route) : redirect) : target
    void loadRouteLocation(destination).catch(() => {})
  }, 90)
}
onBeforeUnmount(cancelPreload)

const isActive = computed(() => {
  const { name, path, meta } = route
  return (name == props.menu.name && path == props.menu.path) || meta?.activeMenu == props.menu.path
})
</script>
<style scoped>
.menu-item-container {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  gap: 6px;
  box-sizing: border-box;
  min-height: 38px;
  padding: 0 14px 0 10px;
  border-radius: 999px;
  color: var(--app-text-color-secondary);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.25;
  white-space: nowrap;
  transition: background-color 160ms ease, color 160ms ease, box-shadow 160ms ease;
}
.menu-icon {
  display: inline-grid;
  place-items: center;
  flex: none;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  font-size: 16px;
  transition: background-color 160ms ease;
}
@media (hover: hover) {
  .menu-item-container:hover {
    color: var(--studio-ink);
    background: var(--app-layout-bg-color);
  }
}
.menu-item-container:active, .menu-item-container.pending {
  color: var(--studio-ink);
  background: var(--studio-selection);
}
.menu-item-container.active {
  color: var(--studio-ink);
  background: color-mix(in srgb, var(--studio-mint) 33%, white);
  box-shadow: inset 0 0 0 1px rgb(22 75 80 / 8%);
  font-weight: 650;
}
.active .menu-icon { background: rgb(255 255 255 / 70%); }
.menu-item-container:focus-visible { outline-offset: -2px; }
@media (max-width: 820px) {
  .menu-item-container { min-height: 44px; }
}
@media (max-width: 550px) {
  .menu-item-container {
    gap: 3px;
    flex: 1 0 auto;
    padding: 0 6px;
    font-size: 13px;
  }
  .menu-icon { width: 17px; height: 20px; font-size: 14px; }
  .active .menu-icon { background: transparent; }
}
</style>
