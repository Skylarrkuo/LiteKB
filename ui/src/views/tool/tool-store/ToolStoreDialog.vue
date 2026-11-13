<template>
  <el-dialog v-model="visible" :title="$t('views.tool.toolStore.title')" append-to-body align-center
    width="min(1060px, calc(100vw - 24px))" class="tool-market-dialog" destroy-on-close>
    <div class="market" data-testid="tool-store">
      <div class="market-controls">
        <el-input v-model="query" clearable prefix-icon="Search" :placeholder="$t('common.search')"
          :aria-label="$t('common.search')" data-testid="store-search" />
        <el-select v-model="category" :empty-values="[null, undefined]" :aria-label="$t('views.tool.toolStore.category')" data-testid="store-category">
          <el-option :value="''" :label="$t('views.tool.toolStore.allCategories')" />
          <el-option v-for="tag in categories" :key="tag.key" :value="tag.key" :label="tag.name" />
        </el-select>
      </div>
      <div v-if="failure" role="alert" class="catalog-error">
        <span>{{ $t('views.tool.toolStore.unavailable') }}</span>
        <el-button text type="primary" :loading="loading" @click="load">{{ $t('studio.refresh') }}</el-button>
      </div>
      <div class="market-results" v-loading="loading" :aria-busy="loading">
        <div v-if="filtered.length" class="store-grid">
          <ToolCard v-for="tool in filtered" :key="tool.id" :tool="tool" :category="getCategory(tool)"
            @add="openInstall(tool)" @detail="detail(tool)" />
        </div>
        <el-empty v-else-if="!loading && !failure" :description="$t('common.noData')" />
      </div>
    </div>
  </el-dialog>
  <InternalDescDrawer ref="details" @add-tool="openInstall" />
  <el-dialog v-model="installOpen" :title="$t('views.tool.toolStore.install')" append-to-body align-center
    width="min(440px, calc(100vw - 24px))" :close-on-click-modal="!installing" :close-on-press-escape="!installing"
    :show-close="!installing">
    <el-form label-position="top" data-testid="store-install-form" @submit.prevent="install">
      <div class="install-target">
        <el-icon aria-hidden="true"><FolderOpened /></el-icon>
        <span>{{ $t('views.tool.library.target') }}</span><strong>{{ folderName }}</strong>
      </div>
      <el-form-item :label="$t('views.tool.form.toolName.label')" required>
        <el-input v-model="installName" maxlength="64" show-word-limit :disabled="installing" data-testid="store-install-name" />
      </el-form-item>
      <el-form-item v-if="selected?.versions?.length" :label="$t('views.tool.toolStore.version')">
        <el-select v-model="version" class="w-full" :disabled="installing" data-testid="store-version">
          <el-option v-for="release in selected.versions" :key="release.name" :label="release.name" :value="release.name" />
        </el-select>
      </el-form-item>
      <p v-if="installError" class="install-error" role="alert">{{ installError }}</p>
      <p v-if="downloadError" class="install-error" role="alert">{{ $t('views.tool.toolStore.downloadFailed') }}</p>
      <div class="install-actions">
        <el-button v-if="selected?.version" text data-testid="store-version-download" :disabled="installing" :loading="downloading" @click="downloadVersion">
          {{ $t('views.document.upload.download') }}
        </el-button>
        <el-button :disabled="installing" @click="installOpen = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" native-type="submit" :disabled="!installName.trim()" :loading="installing"
          data-testid="store-install-submit">{{ $t('common.add') }}</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import ToolStoreApi from '@/api/tool/store'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { MsgSuccess } from '@/utils/message'
import { i18n_name } from '@/utils/common'
import useStore from '@/stores'
import InternalDescDrawer from './InternalDescDrawer.vue'
import ToolCard from './ToolCard.vue'
import { filterCatalog, type CatalogTag, type CatalogTool } from './catalog'

const { t, locale } = useI18n()
const props = withDefaults(defineProps<{ apiType?: 'workspace' | 'systemShare' | 'systemManage' }>(), { apiType: 'workspace' })
const emit = defineEmits<{ refresh: [tool: { id: string }] }>()
const { folder: folderStore } = useStore()
const visible = ref(false)
const loading = ref(false)
const failure = ref(false)
const folder = ref('')
const folderName = ref('')
const query = ref('')
const category = ref('')
const tools = ref<CatalogTool[]>([])
const tags = ref<CatalogTag[]>([])
let requestNumber = 0
const categories = computed(() => {
  const language = locale.value.toLowerCase()
  const key = language.startsWith('en') ? 'en' : language.includes('hant') || language.includes('tw') ? 'zh-hant' : 'zh'
  const names = new Map(tags.value.map(tag => [tag.key, tag.locales?.[key] || tag.name]))
  names.set('internal', t('views.tool.toolStore.internal'))
  names.set('other', t('views.tool.toolStore.other'))
  const used = new Set(tools.value.flatMap(tool => tool.labels?.length ? tool.labels : [tool.label || 'other']))
  return Array.from(used, id => ({ key: id, name: names.get(id) || id }))
})
const filtered = computed(() => filterCatalog(tools.value, query.value, category.value))
function getCategory(tool: CatalogTool) {
  return categories.value.find(tag => tag.key === (tool.label || 'other'))?.name || ''
}
function open(folderId: string, targetName?: string) {
  folder.value = folderId
  folderName.value = targetName || i18n_name(folderStore.currentFolder?.name || folderId)
  visible.value = true
  query.value = ''
  category.value = ''
  load()
}
async function load() {
  const request = ++requestNumber
  failure.value = false
  loading.value = true
  const [remote, internal] = await Promise.allSettled([ToolStoreApi.getStoreToolList(), ToolStoreApi.getInternalToolList()])
  if (request !== requestNumber) return
  failure.value = remote.status === 'rejected' || internal.status === 'rejected'
  const catalog = remote.status === 'fulfilled' ? remote.value.data : undefined
  tags.value = catalog?.additionalProperties?.tags || []
  const builtins = internal.status === 'fulfilled' ? internal.value.data || [] : []
  tools.value = [...(catalog?.apps || []), ...builtins.map((t: CatalogTool) => ({ ...t, labels: ['internal'], label: 'internal' }))]
  loading.value = false
}
const details = ref<InstanceType<typeof InternalDescDrawer>>()
async function detail(tool: CatalogTool) {
  let readme = tool.readMe || ''
  if (tool.tool_type === 'INTERNAL' && tool.icon?.endsWith('/icon.png')) {
    try {
      const url = new URL(tool.icon.replace(/icon\.png$/, 'detail.md'), location.origin)
      if (url.origin === location.origin) {
        const response = await fetch(url, { redirect: 'error' })
        if (response.ok) readme = await response.text()
      }
    } catch { /* The built-in tool's description remains available offline. */ }
  }
  details.value?.open(readme || tool.description || tool.desc || '', tool)
}
const installOpen = ref(false)
const selected = ref<CatalogTool>()
const installName = ref('')
const version = ref('')
const installing = ref(false)
const downloading = ref(false)
const downloadError = ref(false)
const installError = ref('')
function openInstall(tool: CatalogTool) {
  downloadError.value = false
  selected.value = tool
  installName.value = tool.name
  version.value = tool.version || ''
  installError.value = ''
  installOpen.value = true
}
async function downloadVersion() {
  const tool = selected.value
  if (!tool || downloading.value) return
  downloadError.value = false
  const requestedVersion = version.value
  const ok = await ToolStoreApi.downloadStoreTool(tool.id, requestedVersion, downloading)
  if (selected.value?.id === tool.id && version.value === requestedVersion) downloadError.value = !ok
}
async function install() {
  if (!selected.value || !installName.value.trim() || installing.value) return
  installing.value = true
  installError.value = ''
  const tool = selected.value
  let installed
  try {
    const api = loadSharedApi({ type: 'tool', systemType: props.apiType })
    const data = { name: installName.value.trim(), folder_id: folder.value }
    installed = tool.tool_type === 'INTERNAL' ? await api.addInternalTool(tool.id, data)
      : await api.addStoreTool(tool.id, { ...data, version: version.value })
  } catch (error: any) {
    installError.value = error?.code === 409 || error?.response?.data?.code === 409
      ? t('views.tool.toolStore.duplicate') : (error?.response?.data?.message || error?.message || t('views.tool.toolStore.installFailed'))
    return
  } finally {
    installing.value = false
  }
  MsgSuccess(t('common.addSuccess'))
  installOpen.value = false
  visible.value = false
  emit('refresh', installed.data)
}
defineExpose({ open })
</script>
<style scoped lang="scss">
.market { min-width: 0; }
.market-controls { display: flex; align-items: center; gap: 10px; margin: 0 0 14px; }
.market-controls .el-input { flex: 1; }
.market-controls .el-select { width: 200px; }
.market-results { min-height: min(260px, 38dvh); max-height: 65dvh; overflow: auto; padding: 2px; }
.store-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 265px), 1fr)); gap: 12px; }
.catalog-error {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;
  padding: 8px 12px; border: 1px solid var(--studio-hairline); border-radius: var(--app-border-radius-base);
}
.install-actions { display: flex; justify-content: flex-end; align-items: center; gap: 8px; }
.install-target {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding: 10px 12px; margin-bottom: 14px;
  background: var(--studio-selection); color: var(--studio-ink); border-radius: var(--app-border-radius-base);
  strong { overflow-wrap: anywhere; }
}
.install-actions .el-button { margin: 0; }
.install-error { color: var(--el-color-danger); margin-bottom: 10px; }
@media (max-width: 600px) {
  .market-controls { align-items: stretch; flex-direction: column; }
  .market-controls .el-select { width: 100%; }
  .market-results { max-height: 58dvh; }
}
</style>
