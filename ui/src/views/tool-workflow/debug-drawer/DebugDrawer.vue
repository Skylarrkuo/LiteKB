<template>
  <el-drawer
    v-model="visible"
    :title="t('common.debug')"
    append-to-body
    destroy-on-close
    size="min(620px, 100%)"
  >
    <template #header="{ titleId }"
      ><div class="tool-drawer-heading">
        <el-icon aria-hidden="true"><VideoPlay /></el-icon>
        <div>
          <h2 :id="titleId">{{ t('common.debug') }}</h2>
          <p>{{ detail?.name }}</p>
        </div>
      </div></template
    >
    <div class="tool-drawer-body" data-testid="workflow-debug" :aria-busy="loading">
      <el-skeleton v-if="loading" :rows="3" animated />
      <div v-else-if="error" class="tool-notice failed" role="alert">
        {{ error }}
        <el-button link type="primary" @click="getDetail">{{
          t('views.tool.library.retry')
        }}</el-button>
      </div>
      <el-form
        v-else-if="fields.length"
        ref="formRef"
        :model="values"
        label-position="top"
        @submit.prevent
      >
        <h3>{{ t('common.param.inputParam') }}</h3>
        <el-form-item
          v-for="(field, i) in fields"
          :key="field.field"
          :prop="[String(i)]"
          :label="field.label || field.field"
          :required="field.is_required || field.required"
          :rules="rules(field)"
        >
          <template #label
            ><span>{{ field.label || field.field }}</span
            ><code>{{ field.type || 'string' }}</code></template
          >
          <el-select
            v-if="field.type === 'boolean'"
            v-model="values[i]"
            clearable
            :value-on-clear="''"
            :aria-label="field.label || field.field"
            ><el-option label="true" value="true" /><el-option label="false" value="false"
          /></el-select>
          <el-input
            v-else
            v-model="values[i]"
            :aria-label="field.label || field.field"
            :type="['array', 'dict'].includes(field.type) ? 'textarea' : 'text'"
            :autosize="{ minRows: 3, maxRows: 10 }"
            :inputmode="
              field.type === 'int' ? 'numeric' : field.type === 'float' ? 'decimal' : undefined
            "
          />
        </el-form-item>
      </el-form>
      <p v-else class="tool-hint">{{ t('views.tool.debugPanel.noInputs') }}</p>
    </div>
    <template #footer>
      <el-button @click="close">{{ t('common.close') }}</el-button>
      <el-button
        type="primary"
        :icon="VideoPlay"
        :disabled="loading || !!error || !detail"
        data-testid="workflow-debug-run"
        @click="run"
        >{{ t('views.tool.form.debug.run') }}</el-button
      >
    </template>
  </el-drawer>
  <ResultDrawer ref="resultDrawer" />
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { FormInstance, FormItemRule } from 'element-plus'
import { VideoPlay } from '@element-plus/icons-vue'
import { t } from '@/locales'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { errorMessage, inputText, validInput } from '@/views/tool/component/tool-debug'
import ResultDrawer from './ResultDrawer.vue'

interface Field {
  field: string
  label?: string
  type: string
  is_required?: boolean
  required?: boolean
  default_value?: unknown
}
interface Detail {
  id: string
  name?: string
  work_flow?: {
    nodes?: { id: string; type?: string; properties?: { user_input_field_list?: Field[] } }[]
  }
}
const route = useRoute()
const api = computed(() =>
  loadSharedApi({
    type: 'tool',
    isShared: route.params.folderId === 'share',
    systemType: route.path.includes('shared')
      ? 'systemShare'
      : route.path.includes('resource-management')
        ? 'systemManage'
        : route.path.includes('share/')
          ? 'workspaceShare'
          : 'workspace',
  }),
)
const visible = ref(false),
  loading = ref(false),
  error = ref(''),
  id = ref('')
const detail = ref<Detail>(),
  values = ref<string[]>([])
const fields = computed(
  () =>
    detail.value?.work_flow?.nodes?.find(
      (n) => n.id === 'tool-base-node' || n.type === 'tool-base-node',
    )?.properties?.user_input_field_list || [],
)
const resultDrawer = ref<InstanceType<typeof ResultDrawer>>(),
  formRef = ref<FormInstance>()
let request = 0
function rules(f: Field): FormItemRule[] {
  return [
    {
      trigger: 'blur',
      validator: (_r, v, done) => {
        if (!String(v ?? '').trim() && (f.is_required || f.required))
          return done(new Error(t('views.tool.form.param.inputPlaceholder')))
        const unsafeInteger = f.type === 'int' && !!v?.trim() && !Number.isSafeInteger(Number(v))
        if (!validInput(f.type, v ?? '') || unsafeInteger)
          return done(new Error(t('views.tool.debugPanel.expectedType', { type: f.type })))
        done()
      },
    },
  ]
}
function populate(data: Detail) {
  detail.value = data
  values.value = fields.value.map((f) => inputText(f.default_value))
}
async function getDetail() {
  const current = ++request
  loading.value = true
  error.value = ''
  try {
    const res = await api.value.getToolById(id.value)
    if (!res.data?.work_flow?.nodes) throw new Error(t('views.tool.debugPanel.detailError'))
    if (current === request) populate(res.data)
  } catch (e) {
    if (current === request) error.value = errorMessage(e, t('views.tool.debugPanel.detailError'))
  } finally {
    if (current === request) loading.value = false
  }
}
function open(toolId: string, data?: Detail) {
  ++request
  resultDrawer.value?.close()
  id.value = toolId
  detail.value = undefined
  values.value = []
  error.value = ''
  loading.value = false
  visible.value = true
  if (data?.id === toolId && data.work_flow?.nodes) populate(data)
  else getDetail()
}
function close() {
  visible.value = false
}
watch(
  visible,
  (show) => {
    if (!show) {
      ++request
      detail.value = undefined
      values.value = []
      resultDrawer.value?.close()
    }
  },
  { flush: 'sync' },
)
async function run() {
  if (loading.value || !detail.value || error.value) return
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const payload = Object.fromEntries(
    fields.value.flatMap((field, i) => {
      const raw = values.value[i] ?? ''
      if (!raw.trim()) return []
      const value =
        field.type === 'boolean'
          ? raw === 'true'
          : field.type === 'array' || field.type === 'dict'
            ? JSON.parse(raw)
            : ['int', 'float'].includes(field.type)
              ? Number(raw)
              : raw
      return [[field.field, value]]
    }),
  )
  resultDrawer.value?.open(id.value, payload)
}
defineExpose({ open, close })
</script>
<style scoped src="../../tool/component/tool-panel.css"></style>
