<template>
  <div class="studio-main-content">
    <router-view v-slot="{ Component }">
      <keep-alive :include="cachedViews">
        <component :is="Component" :key="viewKey" />
      </keep-alive>
    </router-view>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onBeforeUpdate } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const viewKey = computed(() => route.matched.some(record => record.name === 'settings') ? 'settings' : route.path)

const cachedViews: any = ref([])
onBeforeUpdate(() => {
  const { name } = route
  if (name && !cachedViews.value.includes(name)) {
    cachedViews.value.push(name)
  }
})
</script>
<style scoped>
.studio-main-content { height: 100%; min-width: 0; }
</style>
