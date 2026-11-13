<template>
  <article class="store-card" :data-tool-id="tool.id">
    <header>
      <span class="tool-mark" aria-hidden="true">
        <img v-if="tool.icon && !iconFailed" :src="resetUrl(tool.icon)" loading="lazy" alt="" @error="iconFailed = true" />
        <el-icon v-else><Tools /></el-icon>
      </span>
      <div class="tool-heading">
        <h4>{{ tool.name }}</h4>
        <p>{{ category }}<span v-if="tool.version"> · {{ tool.version }}</span></p>
      </div>
    </header>
    <p class="tool-desc">{{ tool.description || tool.desc }}</p>
    <p v-if="downloadError" role="alert" class="download-error">{{ $t('views.tool.toolStore.downloadFailed') }}</p>
    <footer>
      <el-button text @click="$emit('detail')">{{ $t('common.detail') }}</el-button>
      <el-button v-if="tool.tool_type !== 'INTERNAL'" text data-testid="store-download" :loading="downloading"
        @click="download">{{ $t('views.document.upload.download') }}</el-button>
      <el-button plain type="primary" data-testid="store-add" @click="$emit('add')">{{ $t('common.add') }}</el-button>
    </footer>
  </article>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { Tools } from '@element-plus/icons-vue'
import ToolStoreApi from '@/api/tool/store'
import { resetUrl } from '@/utils/common'
import type { CatalogTool } from './catalog'
const props = defineProps<{ tool: CatalogTool; category: string }>()
defineEmits<{ add: []; detail: [] }>()
const iconFailed = ref(false)
const downloading = ref(false)
const downloadError = ref(false)
async function download() {
  if (!props.tool.version || downloading.value) return
  downloadError.value = false
  downloadError.value = !await ToolStoreApi.downloadStoreTool(props.tool.id, props.tool.version, downloading)
}
</script>
<style scoped lang="scss">
.download-error { color:var(--el-color-danger-dark-2); overflow-wrap:anywhere; }
.store-card {
  display: flex; flex-direction: column; gap: 12px; min-width: 0;
  padding: 15px; border: 1px solid var(--studio-hairline);
  border-radius: var(--app-border-radius-base); background: var(--app-view-bg-color);
  &:focus-within { border-color: var(--studio-ink); }
  header, footer { display: flex; align-items: center; gap: 8px; }
  .tool-mark {
    width: 34px; height: 34px; background: var(--studio-selection); color: var(--studio-ink);
    border-radius: var(--app-border-radius-base); display: grid; place-items: center; flex: none;
    img { width: 100%; height: 100%; object-fit: contain; border-radius: inherit; }
  }
  .tool-heading { min-width: 0; }
  h4 { font-size: 15px; line-height: 1.4; color: var(--studio-ink); overflow-wrap: anywhere; }
  .tool-heading p { font-size: 12px; margin: 2px 0 0; color: var(--app-text-color-secondary); }
  .tool-desc {
    font-size: 13px; line-height: 1.55; margin: 0; overflow-wrap: anywhere;
    color: var(--app-text-color-secondary); display: -webkit-box; -webkit-box-orient: vertical;
    -webkit-line-clamp: 3; overflow: hidden;
  }
  footer { justify-content: flex-end; flex-wrap: wrap; margin-top: auto; }
  footer .el-button { margin: 0; }
}
</style>
