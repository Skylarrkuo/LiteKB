<template>
  <el-drawer
    v-model="visible"
    size="min(620px, 100%)"
    :title="t('common.debug')"
    append-to-body
    destroy-on-close
  >
    <template #header="{ titleId }">
      <div class="tool-drawer-heading">
        <el-icon aria-hidden="true"><VideoPlay /></el-icon>
        <div>
          <h2 :id="titleId">{{ t('common.debug') }}</h2>
          <p v-if="toolName">{{ toolName }}</p>
        </div>
      </div>
    </template>
    <div class="tool-drawer-body" data-testid="tool-debug">
      <p v-if="unavailable" role="status" class="tool-notice">{{ unavailable }}</p>
      <p v-else-if="isMcp" class="tool-hint">{{ t('views.tool.debugPanel.mcpHelp') }}</p>
      <p v-else-if="savedId && fields.length" class="tool-hint">
        {{ t('views.tool.debugPanel.storedParams') }}
      </p>
      <section v-if="!savedId && fields.length">
        <h3>{{ t('common.param.initParam') }}</h3>
        <DynamicsForm
          :key="formSession"
          v-model="params"
          :model="params"
          :render_data="fields"
          ref="initForm"
          default-item-width="100%"
          :disabled="sending"
        />
      </section>
      <section v-if="inputs.length">
        <h3>{{ t('common.param.inputParam') }}</h3>
        <el-form
          ref="inputForm"
          :model="values"
          label-position="top"
          :disabled="sending"
          @submit.prevent
        >
          <el-form-item
            v-for="(field, index) in inputs"
            :key="field.name"
            :label="field.name"
            :prop="[String(index)]"
            :required="field.is_required"
            :rules="inputRules(field)"
          >
            <template #label
              ><span>{{ field.name }}</span
              ><code>{{ field.type || 'string' }}</code></template
            >
            <el-select
              v-if="field.type === 'boolean'"
              v-model="values[index]"
              clearable
              :value-on-clear="''"
              :aria-label="field.name"
            >
              <el-option label="true" value="true" /><el-option label="false" value="false" />
            </el-select>
            <el-input
              v-else
              v-model="values[index]"
              :aria-label="field.name"
              :type="['dict', 'array'].includes(field.type || '') ? 'textarea' : 'text'"
              :autosize="{ minRows: 3, maxRows: 10 }"
              :inputmode="
                field.type === 'int' ? 'numeric' : field.type === 'float' ? 'decimal' : undefined
              "
            />
            <p v-if="field.desc" class="tool-help">{{ field.desc }}</p>
          </el-form-item>
        </el-form>
      </section>
      <p v-else-if="!fields.length && !isMcp && !unavailable" class="tool-hint">
        {{ t('views.tool.debugPanel.noInputs') }}
      </p>
      <section
        v-if="outcome"
        class="tool-result"
        :class="{ failed: !outcome.ok }"
        data-testid="tool-debug-result"
      >
        <h3 :role="outcome.ok ? 'status' : 'alert'">
          <el-icon aria-hidden="true"
            ><SuccessFilled v-if="outcome.ok" /><WarningFilled v-else
          /></el-icon>
          {{
            outcome.ok
              ? t('views.tool.form.debug.runSuccess')
              : t('views.tool.form.debug.runFailed')
          }}
        </h3>
        <pre tabindex="0" :aria-label="t('views.tool.form.debug.output')">{{
          formatOutput(outcome.output)
        }}</pre>
      </section>
    </div>
    <template #footer>
      <el-button @click="visible = false">{{ t('common.close') }}</el-button>
      <el-button
        type="primary"
        :icon="VideoPlay"
        :loading="sending"
        :disabled="!!unavailable"
        data-testid="tool-debug-run"
        @click="submit"
      >
        {{ isMcp ? t('views.tool.debugPanel.testConnection') : t('views.tool.form.debug.run') }}
      </el-button>
    </template>
  </el-drawer>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { cloneDeep } from 'lodash'
import type { FormInstance, FormItemRule } from 'element-plus'
import { VideoPlay, WarningFilled, SuccessFilled } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { t } from '@/locales'
import DynamicsForm from '@/components/dynamics-form/index.vue'
import type { FormField } from '@/components/dynamics-form/type'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import {
  errorMessage,
  formatOutput,
  initialParams,
  inputText,
  validInput,
  type DebugResult,
  type ToolDefinition,
  type ToolInput,
} from './component/tool-debug'
const emit = defineEmits<{ result: [result: DebugResult] }>()
const route = useRoute()
const apiType = computed(() =>
  route.path.includes('shared')
    ? 'systemShare'
    : route.path.includes('resource-management')
      ? 'systemManage'
      : 'workspace',
)
const visible = ref(false),
  sending = ref(false),
  savedId = ref(''),
  toolName = ref(''),
  code = ref(''),
  unavailable = ref('')
const isMcp = ref(false)
const formSession = ref(0)
const inputs = ref<ToolInput[]>([]),
  fields = ref<FormField[]>([]),
  values = ref<string[]>([])
const params = ref<Record<string, any>>({}),
  outcome = ref<DebugResult>()
const inputForm = ref<FormInstance>(),
  initForm = ref<InstanceType<typeof DynamicsForm>>()
let sequence = 0

function inputRules(field: ToolInput): FormItemRule[] {
  return [
    {
      trigger: 'blur',
      validator: (_rule, v, done) => {
        if (!String(v ?? '').trim() && field.is_required)
          done(new Error(t('views.tool.form.param.inputPlaceholder')))
        else if (!validInput(field.type, v ?? ''))
          done(new Error(t('views.tool.debugPanel.expectedType', { type: field.type })))
        else done()
      },
    },
  ]
}

function reset() {
  ++sequence
  sending.value = false
  outcome.value = undefined
  code.value = ''
  savedId.value = ''
  values.value = []
  fields.value = []
  inputs.value = []
  params.value = {}
  unavailable.value = ''
  isMcp.value = false
}
watch(
  visible,
  (show) => {
    if (!show) reset()
  },
  { flush: 'sync' },
)

function start(data: ToolDefinition, saved: boolean) {
  reset()
  ++formSession.value
  toolName.value = data.name || ''
  savedId.value = saved ? data.id || '' : ''
  isMcp.value = saved && data.execution?.debug_mode === 'mcp'
  if (
    saved &&
    (!savedId.value ||
      (data.execution &&
        (!['python', 'mcp'].includes(data.execution.debug_mode) || !data.execution.available)))
  ) {
    unavailable.value = data.execution?.reason || t('views.tool.debugPanel.unavailable')
  }
  code.value = saved ? '' : data.code || ''
  inputs.value = isMcp.value ? [] : cloneDeep(data.input_field_list || [])
  values.value = inputs.value.map((f) => inputText(f.value ?? f.default_value))
  fields.value = cloneDeep(data.init_field_list || [])
  if (!saved) {
    // Unpublished draft code must never receive an installed tool's stored credential.
    if (data.id)
      fields.value
        .filter((f) => f.input_type === 'PasswordInput')
        .forEach((f) => {
          delete f.default_value
        })
    params.value = initialParams(fields.value, data.init_params, !!data.id)
  }
  visible.value = true
}
function open(data: ToolDefinition) {
  start(data, false)
}
function openSaved(data: ToolDefinition) {
  start(data, true)
}
async function submit() {
  if (sending.value || unavailable.value) return
  const request = ++sequence
  sending.value = true
  try {
    try {
      await Promise.all([initForm.value?.validate(), inputForm.value?.validate()])
    } catch {
      return
    }
    if (request !== sequence) return
    const debug_field_list = inputs.value.map((field, i) => ({
      name: field.name,
      value: values.value[i] ?? '',
    }))
    const api = loadSharedApi({ type: 'tool', systemType: apiType.value })
    const res = savedId.value
      ? await api.postSavedToolDebug(savedId.value, { debug_field_list })
      : await api.postToolDebug({
          code: code.value,
          input_field_list: inputs.value.map(({ value, ...field }) => field),
          init_field_list: fields.value,
          init_params: params.value,
          debug_field_list,
        })
    if (request !== sequence) return
    outcome.value =
      res.code === 200
        ? { ok: true, output: res.data }
        : { ok: false, output: res.message || t('views.tool.form.debug.runFailed') }
  } catch (e) {
    if (request !== sequence) return
    outcome.value = { ok: false, output: errorMessage(e, t('views.tool.form.debug.runFailed')) }
  } finally {
    if (request === sequence) sending.value = false
  }
  if (outcome.value) emit('result', outcome.value)
}
defineExpose({ open, openSaved })
</script>
<style scoped src="./component/tool-panel.css"></style>
