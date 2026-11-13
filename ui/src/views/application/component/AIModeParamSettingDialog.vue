<template>
  <el-dialog
    align-center
    :title="$t('common.paramSetting')"
    v-model="dialogVisible"
    width="min(550px, calc(100vw - 24px))"
    append-to-body
    destroy-on-close
    :close-on-click-modal="false"
    :close-on-press-escape="false"
  >
    <!-- loading 遮罩:getModelParamsForm 异步期间(loading=true)以遮罩盖住 body,
         避免 show 到 render() 之间闪现上一次打开的模型参数内容/空白 -->
    <div v-loading="loading" class="param-setting-dialog-body">
      <DynamicsForm
        v-if="ready"
        v-model="form_data"
        :model="form_data"
        default-item-width="100%"
        label-position="top"
        require-asterisk-position="right"
        :render_data="model_form_field"
        ref="dynamicsFormRef"
      >
      </DynamicsForm>
      <p v-if="ready && model_form_field.length === 0" class="no-parameters">
        {{ $t('views.model.tip.emptyMessage2') }}
      </p>
    </div>

    <template #footer>
      <span class="dialog-footer">
        <el-button @click.prevent="dialogVisible = false">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="primary" @click="submit" :loading="loading" :disabled="!ready">
          {{ $t('common.confirm') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FormField } from '@/components/dynamics-form/type'
import { useRoute } from 'vue-router'
import DynamicsForm from '@/components/dynamics-form/index.vue'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'

const route = useRoute()
const apiType = computed(() => {
  if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})
const model_form_field = ref<Array<FormField>>([])
const emit = defineEmits(['refresh'])
const dynamicsFormRef = ref<InstanceType<typeof DynamicsForm>>()
const form_data = ref<any>({})
const dialogVisible = ref(false)
const loading = ref(false)
const ready = ref(false)
let revision = 0
const getApi = (modelId: string) =>
  loadSharedApi({ type: 'model', systemType: apiType.value }).getModelParamsForm(modelId)

const open = async (
  modelId: string,
  _applicationId?: string,
  values?: any,
  providedFields?: FormField[],
) => {
  const current = ++revision
  ready.value = false
  model_form_field.value = []
  form_data.value = {}
  dialogVisible.value = true
  loading.value = !providedFields
  try {
    const fields = providedFields ?? (await getApi(modelId)).data
    if (current !== revision || !dialogVisible.value) return
    model_form_field.value = fields
    form_data.value = values || {}
    ready.value = true
  } finally {
    if (current === revision) loading.value = false
  }
}

const reset_default = async (modelId: string, _applicationId?: string) => {
  const current = ++revision
  loading.value = false
  const { data } = await getApi(modelId)
  if (current !== revision) return
  emit('refresh', Object.fromEntries(data.map((field: FormField) => [
    field.field, field.show_default_value === false ? undefined : field.default_value,
  ])))
}

const submit = async () => {
  dynamicsFormRef.value?.validate().then(() => {
    emit('refresh', form_data.value)
    dialogVisible.value = false
  })
}

defineExpose({ open, reset_default })
</script>

<style lang="scss" scoped>
.param-setting-dialog-body {
  min-height: 120px;
  max-height: min(60dvh, 620px);
  padding: 3px;
  overflow-y: auto;
}
.no-parameters {
  margin: 32px 0;
  text-align: center;
  color: var(--app-text-color-secondary);
}
</style>
