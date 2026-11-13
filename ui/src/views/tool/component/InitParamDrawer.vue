<template>
  <el-drawer
    v-model="visible"
    size="min(560px, 100%)"
    :title="t('common.param.initParam')"
    append-to-body
    destroy-on-close
    :close-on-click-modal="!sending"
    :close-on-press-escape="!sending"
    :show-close="!sending"
  >
    <template #header="{ titleId }"
      ><div class="tool-drawer-heading">
        <el-icon aria-hidden="true"><Setting /></el-icon>
        <div>
          <h2 :id="titleId">{{ t('common.param.initParam') }}</h2>
          <p v-if="toolName">{{ toolName }}</p>
        </div>
      </div></template
    >
    <div class="tool-drawer-body" data-testid="tool-init-params">
      <p v-if="hasPassword" class="tool-hint">{{ t('views.tool.debugPanel.maskHint') }}</p>
      <DynamicsForm
        :key="formSession"
        v-if="fields.length"
        ref="initForm"
        v-model="values"
        :model="values"
        :render_data="fields"
        default-item-width="100%"
        :disabled="sending"
      />
      <p v-else class="tool-hint">{{ t('views.tool.debugPanel.noParams') }}</p>
      <p v-if="error" role="alert" class="tool-notice failed">{{ error }}</p>
    </div>
    <template #footer>
      <el-button :disabled="sending" @click="visible = false">{{ t('common.cancel') }}</el-button>
      <el-button
        type="primary"
        :loading="sending"
        :disabled="!toolId || (!fields.length && activate === undefined)"
        data-testid="tool-init-save"
        @click="submit"
        >{{ t('common.save') }}</el-button
      >
    </template>
  </el-drawer>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { cloneDeep } from 'lodash'
import { Setting } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { t } from '@/locales'
import { MsgSuccess } from '@/utils/message'
import DynamicsForm from '@/components/dynamics-form/index.vue'
import type { FormField } from '@/components/dynamics-form/type'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { errorMessage, initialParams, type ToolDefinition } from './tool-debug'

const emit = defineEmits<{ refresh: []; saved: [data: { id: string }] }>()
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
  toolId = ref(''),
  toolName = ref(''),
  error = ref('')
const fields = ref<FormField[]>([]),
  values = ref<Record<string, any>>({}),
  activate = ref<boolean>()
const initForm = ref<InstanceType<typeof DynamicsForm>>()
const hasPassword = computed(() => fields.value.some((f) => f.input_type === 'PasswordInput'))
const formSession = ref(0)
let sequence = 0
function clear() {
  ++sequence
  sending.value = false
  error.value = ''
  fields.value = []
  values.value = {}
  toolId.value = ''
  activate.value = undefined
}
watch(
  visible,
  (show) => {
    if (!show) clear()
  },
  { flush: 'sync' },
)
function open(data: ToolDefinition, isActive?: boolean) {
  clear()
  ++formSession.value
  toolId.value = data.id || ''
  toolName.value = data.name || ''
  fields.value = cloneDeep(data.init_field_list || [])
  values.value = initialParams(fields.value, data.init_params)
  activate.value = isActive
  visible.value = true
}
async function submit() {
  if (sending.value || !toolId.value) return
  const id = toolId.value
  const request = ++sequence
  sending.value = true
  error.value = ''
  try {
    try {
      await initForm.value?.validate()
    } catch {
      return
    }
    if (request !== sequence) return
    const payload = {
      init_params: values.value,
      ...(activate.value !== undefined ? { is_active: activate.value } : {}),
    }
    await loadSharedApi({ type: 'tool', systemType: apiType.value }).putTool(id, payload)
  } catch (e) {
    if (request === sequence) error.value = errorMessage(e, t('views.tool.debugPanel.saveError'))
    return
  } finally {
    if (request === sequence) sending.value = false
  }
  if (request !== sequence) return
  visible.value = false
  MsgSuccess(t('common.editSuccess'))
  emit('saved', { id })
  emit('refresh')
}
defineExpose({ open })
</script>
<style src="./tool-panel.css" scoped></style>
