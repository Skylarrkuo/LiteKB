<template>
  <el-drawer v-model="visible" :title="$t('views.tool.detail.title')" append-to-body destroy-on-close
    size="min(610px, 100vw)" class="installed-tool-drawer" @close="invalidate">
    <div data-testid="tool-detail" class="tool-detail">
      <header class="identity">
        <img v-if="tool.icon && !brokenIcon" :src="resetUrl(tool.icon)" alt="" @error="brokenIcon = true" />
        <ToolIcon v-else :size="44" :type="tool.tool_type" />
        <div>
          <h2>{{ tool.name }}</h2>
          <span class="state" :class="{ active: tool.is_active }">
            {{ $t(tool.is_active ? 'common.status.enabled' : 'common.status.disabled') }}
          </span>
          <span v-if="tool.version" class="version">{{ tool.version }}</span>
        </div>
      </header>
      <p v-if="tool.desc" class="summary">{{ tool.desc }}</p>
      <el-skeleton v-if="loading" animated :rows="3" />
      <div v-else-if="error" role="alert" class="notice">
        {{ $t('views.tool.detail.loadError') }}
        <el-button link type="primary" @click="load(tool)">{{ $t('views.tool.library.retry') }}</el-button>
      </div>
      <template v-else>
        <section class="parameter-group">
          <header><h3>{{ $t('common.param.initParam') }}</h3>
            <el-button v-if="canEdit && tool.init_field_list?.length" text type="primary"
              data-testid="detail-configure" @click="emit('configure', tool)">{{ $t('common.paramSetting') }}</el-button>
          </header>
          <p v-if="!tool.init_field_list?.length">{{ $t('views.tool.detail.noInit') }}</p>
          <dl v-else>
            <div v-for="field in tool.init_field_list" :key="field.field">
              <dt>{{ typeof field.label === 'string' ? field.label : field.field }}
                <code v-if="field.label && field.label !== field.field">{{ field.field }}</code>
              </dt>
              <dd>{{ $t(hasStartupValue(tool, field) ? 'views.tool.detail.configured' : field.required ? 'views.tool.detail.missing' : 'views.tool.detail.optional') }}</dd>
            </div>
          </dl>
        </section>
        <section v-if="tool.input_field_list?.length" class="parameter-group">
          <header><h3>{{ $t('common.param.inputParam') }}</h3></header>
          <dl><div v-for="field in tool.input_field_list" :key="field.name">
            <dt><code>{{ field.name }}</code><span v-if="field.desc">{{ field.desc }}</span></dt>
            <dd>{{ field.type }}<span v-if="field.is_required"> · {{ $t('common.required') }}</span></dd>
          </div></dl>
        </section>
        <details v-if="readme" class="documentation">
          <summary>{{ $t('views.tool.detail.instructions') }}</summary>
          <MdPreview :editorId="'installed-help-' + tool.id" :modelValue="readme" noImgZoomIn />
        </details>
        <p v-if="tool.execution && !tool.execution.available && tool.execution.reason" class="notice" role="status">
          {{ tool.execution.reason }}
        </p>
      </template>
    </div>
    <template #footer>
      <div v-if="!error && !loading" class="actions">
        <el-button v-if="canEdit" @click="emit('edit', tool)" data-testid="detail-edit">{{ $t(tool.template_id ? 'common.rename' : 'common.edit') }}</el-button>
        <el-button v-if="canDebug && debugMode && debugMode !== 'none'"
          data-testid="detail-debug" :disabled="!tool.execution?.available" @click="emit('debug', tool)">
          {{ $t(debugMode === 'workflow' ? 'views.tool.detail.debugWorkflow' : debugMode === 'mcp' ? 'views.tool.detail.testConnection' : 'common.debug') }}
        </el-button>
        <el-button v-if="canSwitch" :type="tool.is_active ? 'default' : 'primary'" data-testid="detail-activate"
          :loading="switchBusy" @click="emit('toggle', tool)">
          {{ $t(tool.is_active ? 'common.status.disable' : 'common.status.enable') }}
        </el-button>
      </div>
    </template>
  </el-drawer>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { resetUrl } from '@/utils/common'
import { hasStartupValue } from '../startup-values'
const props = defineProps<{
  fetchTool: (id: string) => Promise<any>
  catalog: { id: string; readMe?: string }[]
  editable: (id: string) => boolean
  debuggable: (id: string) => boolean
  switchable: (id: string) => boolean
  switchBusy: boolean
}>()
const emit = defineEmits<{ configure: [tool: any]; edit: [tool: any]; debug: [tool: any]; toggle: [tool: any] }>()
const visible = ref(false)
const loading = ref(false)
const error = ref(false)
const brokenIcon = ref(false)
const tool = ref<any>({})
let request = 0
const canEdit = computed(() => !!tool.value.id && props.editable(tool.value.id))
const canDebug = computed(() => !!tool.value.id && props.debuggable(tool.value.id))
const canSwitch = computed(() => !!tool.value.id && props.switchable(tool.value.id))
const debugMode = computed(() => tool.value.execution?.debug_mode)
const readme = computed(() => props.catalog.find(entry => entry.id === tool.value.template_id)?.readMe)
function invalidate() { ++request }
async function load(row: any) {
  const current = ++request
  loading.value = true
  error.value = false
  try {
    const result = await props.fetchTool(row.id)
    if (current === request) tool.value = result.data
  } catch {
    if (current === request) error.value = true
  } finally {
    if (current === request) loading.value = false
  }
}
function open(row: any) {
  if (!row?.id) return
  tool.value = row
  brokenIcon.value = false
  visible.value = true
  return load(row)
}
function reload(id: string) {
  if (visible.value && tool.value.id === id) return load(tool.value)
}
defineExpose({ open, reload })
</script>
<style scoped>
.tool-detail { display: grid; gap: 18px; min-width: 0; color: var(--studio-ink); overflow-wrap: anywhere; }
.identity, .parameter-group header, .actions { display: flex; align-items: center; gap: 12px; }
.identity img { width: 44px; height: 44px; object-fit: contain; border-radius: 12px; }
.identity h2 { font-size: 22px; line-height: 1.3; margin: 0 0 6px; }
.state, .version, .parameter-group dd { font-size: 12px; }
.state { display: inline-flex; align-items: center; gap: 5px; color: var(--app-text-color-secondary); }
.state::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.state.active { color: var(--el-color-success-dark-2); }
.version { margin-left: 10px; }
.summary, .notice { margin: 0; line-height: 1.55; white-space: pre-line; }
.parameter-group { border: 1px solid var(--studio-hairline); border-radius: var(--app-border-radius-large); overflow: hidden; }
.parameter-group header { min-height: 46px; justify-content: space-between; padding: 4px 14px; background: var(--app-layout-bg-color); }
.parameter-group h3 { font-size: 14px; margin: 0; }
.parameter-group p, .parameter-group dl > div { margin: 0; padding: 12px 14px; }
.parameter-group dl { margin: 0; }
.parameter-group dl > div { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.parameter-group dl > div + div { border-top: 1px solid var(--studio-hairline); }
.parameter-group dt > span, .parameter-group dt > code:not(:first-child) { display: block; font-size: 12px; }
.parameter-group dd, .parameter-group p, .parameter-group dt > span, .summary { color: var(--app-text-color-secondary); }
.parameter-group dd { flex-shrink: 0; margin: 0; }
.documentation { min-width: 0; }
.documentation summary { cursor: pointer; font-weight: 600; }
.documentation :deep(.md-editor-preview-wrapper) { overflow: auto; }
.notice { padding: 12px 14px; border-radius: var(--app-border-radius-base); background: var(--studio-selection); }
.actions { justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.actions :deep(.el-button) { margin: 0; }
:global(.installed-tool-drawer.el-drawer) { border-radius: 20px 0 0 20px; max-width: 100%; }
:global(.installed-tool-drawer .el-drawer__footer) { border-top: 1px solid var(--studio-hairline); }
@media (max-width: 600px) { :global(.installed-tool-drawer.el-drawer) { border-radius: 0; } }
</style>
