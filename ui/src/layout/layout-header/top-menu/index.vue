<template>
  <nav ref="navigation" class="top-menu-container" :aria-label="$t('studio.navigation')">
    <MenuItem
      :menu="menu"
      v-hasPermission="menu.meta?.permission"
      v-for="menu in topMenuList"
      :key="menu.path"
    >
    </MenuItem>
  </nav>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { topMenuRoutes } from '@/router/routes'
import { hasPermission } from '@/utils/permission/index'
import MenuItem from './MenuItem.vue'

const navigation = ref<HTMLElement>()
const route = useRoute()
watch(
  () => route.path,
  async () => {
    await nextTick()
    const nav = navigation.value
    const active = nav?.querySelector<HTMLElement>('[aria-current="page"]')
    if (nav && active && nav.scrollWidth > nav.clientWidth) {
      nav.scrollLeft +=
        active.getBoundingClientRect().left -
        nav.getBoundingClientRect().left -
        (nav.clientWidth - active.clientWidth) / 2
    }
  },
  { immediate: true },
)

const topMenuList = computed(() => topMenuRoutes.filter(
  item => !item.meta?.permission || hasPermission(item.meta.permission as any, 'OR'),
))
</script>
<style scoped>
.top-menu-container {
  display: flex;
  align-items: center;
  gap: 3px;
  box-sizing: border-box;
  padding: 4px;
  background: #eaf0ed;
  border: 1px solid #dce6e0;
  border-radius: 14px;
  overflow-x: auto;
  scrollbar-width: none;
}
.top-menu-container::-webkit-scrollbar {
  display: none;
}
@media (max-width: 820px) {
  .top-menu-container {
    width: 100%;
    justify-content: safe center;
  }
}
</style>
