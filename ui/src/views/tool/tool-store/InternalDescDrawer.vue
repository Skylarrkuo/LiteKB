<template>
  <el-drawer v-model="visible" :title="$t('views.tool.detail.title')" append-to-body destroy-on-close
    size="min(680px, 100vw)" class="catalog-tool-detail">
    <template v-if="tool">
      <header class="intro">
        <span class="mark">
          <img v-if="tool.icon && !brokenIcon" :src="resetUrl(tool.icon)" alt="" @error="brokenIcon = true" />
          <el-icon v-else><Tools /></el-icon>
        </span>
        <div><h2>{{ tool.name }}</h2><small v-if="tool.version">{{ $t('views.tool.toolStore.version') }} {{ tool.version }}</small></div>
      </header>
      <p v-if="description" class="summary">{{ description }}</p>
      <MdPreview v-if="readme && readme !== description" :editorId="'catalog-help-' + tool.id" :modelValue="readme" noImgZoomIn />
    </template>
    <template #footer>
      <el-button type="primary" @click="add">{{ $t('views.tool.toolStore.install') }}</el-button>
    </template>
  </el-drawer>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { Tools } from '@element-plus/icons-vue'
import { resetUrl } from '@/utils/common'
import type { CatalogTool } from './catalog'
const emit = defineEmits<{ addTool: [tool: CatalogTool] }>()
const visible = ref(false)
const brokenIcon = ref(false)
const readme = ref('')
const tool = ref<CatalogTool>()
const description = computed(() => tool.value?.description || tool.value?.desc)
function open(markdown: string, row: CatalogTool) {
  tool.value = row
  readme.value = markdown
  brokenIcon.value = false
  visible.value = true
}
function add() {
  if (tool.value) emit('addTool', tool.value)
  visible.value = false
}
defineExpose({ open })
</script>
<style scoped>
.intro { display: flex; align-items: center; gap: 12px; color: var(--studio-ink); }
.mark { flex: none; width: 44px; height: 44px; display: grid; place-items: center; border-radius: 12px; overflow: hidden; background: var(--studio-selection); }
.mark img { width: 100%; height: 100%; object-fit: contain; }
.intro h2 { margin: 0; overflow-wrap: anywhere; line-height: 1.35; font-size: 22px; }
.summary { margin: 14px 0; color: var(--app-text-color-secondary); line-height: 1.6; overflow-wrap: anywhere; }
:global(.catalog-tool-detail.el-drawer) { max-width: 100%; border-radius: 20px 0 0 20px; }
@media (max-width: 600px) { :global(.catalog-tool-detail.el-drawer) { border-radius: 0; } }
</style>
