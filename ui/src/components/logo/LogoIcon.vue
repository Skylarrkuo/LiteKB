<template>
  <img :src="brandIcon" alt="" :style="{ height, width: height }" class="brand-icon" />
</template>
<script setup lang="ts">
import { brandIcon } from '@/utils/branding'
defineOptions({ name: 'LogoIcon' })
withDefaults(defineProps<{ height?: string }>(), { height: '32px' })
</script>
<style scoped>
.brand-icon {
  display: inline-block;
  object-fit: contain;
  vertical-align: middle;
}
</style>
