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
  gap: 2px;
  box-sizing: border-box;
  padding: 4px;
  background: #fff;
  border: 1px solid var(--studio-hairline);
  border-radius: 999px;
  box-shadow: 0 2px 6px rgb(22 75 80 / 4%);
  overflow-x: auto;
  scrollbar-width: none;
}
.top-menu-container::-webkit-scrollbar {
  display: none;
}
@media (max-width: 820px) {
  .top-menu-container {
    width: 100%;
    padding: 2px;
    justify-content: safe center;
  }
}
</style>
