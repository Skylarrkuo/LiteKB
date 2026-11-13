<template>
  <router-link
    class="menu-item-container"
    :class="isActive ? 'active' : ''"
    :to="{ name: menu.name }"
    :title="$t(menu.meta?.title as string)"
    :aria-label="$t(menu.meta?.title as string)"
    :aria-current="isActive ? 'page' : undefined"
  >
    <div class="title flex align-center">
      <AppIcon
        :iconName="isActive ? menu.meta?.iconActive || menu.meta?.icon : menu?.meta?.icon"
        style="font-size: 16px"
        aria-hidden="true"
      />
      <span class="title-text"> {{ $t(menu.meta?.title as string) }}</span>
    </div>
  </router-link>
</template>
<script setup lang="ts">
import { useRoute, type RouteRecordRaw } from 'vue-router'
import { computed } from 'vue'

const route = useRoute()

const props = defineProps<{
  menu: RouteRecordRaw
}>()

const isActive = computed(() => {
  const { name, path, meta } = route
  return (name == props.menu.name && path == props.menu.path) || meta?.activeMenu == props.menu.path
})
</script>
<style lang="scss" scoped>
.menu-item-container {
  flex: 0 0 auto;
  color: #465b54;
  text-decoration: none;
  cursor: pointer;
  font-size: 14px;
  position: relative;
  padding: 8px 14px;
  line-height: 18px;
  white-space: nowrap;
  font-weight: 550;
  border-radius: 10px;
  .title {
    gap: 6px;
  }
  &:focus-visible {
    outline-offset: -2px;
  }
  &:hover {
    background-color: #dce7e0;
  }
  &.active {
    background-color: var(--studio-ink);
    color: white;
    box-shadow: 0 1px 3px rgb(22 75 80 / 14%);
    :deep(.app-icon), :deep(.el-icon) { color: var(--studio-mint); }
    &:focus-visible { outline-color: var(--studio-mint) !important; }
  }
}
@media (max-width: 1050px) {
  .menu-item-container {
    padding: 8px 10px;
  }
}
@media (max-width: 550px) {
  .menu-item-container {
    padding: 8px 6px;
    font-size: 13px;
  }
  .menu-item-container .title {
    gap: 3px;
  }
  .menu-item-container .title :deep(svg) {
    width: 14px;
  }
}
</style>
