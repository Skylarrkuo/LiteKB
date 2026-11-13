<template>
  <el-dialog
    v-model="dialogVisible"
    width="min(680px, calc(100vw - 24px))"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :destroy-on-close="true"
    :before-close="close"
    append-to-body
  >
    <template #header>
      <el-breadcrumb separator=">">
        <el-breadcrumb-item>
          <button type="button" @click="toSelectProvider" class="select-provider">
            {{ $t('views.model.providerPlaceholder') }}
          </button>
        </el-breadcrumb-item>
        <el-breadcrumb-item
          ><span class="active-breadcrumb">{{
            `${$t('common.add')} ${providerValue?.name}`
          }}</span></el-breadcrumb-item
        >
      </el-breadcrumb>
    </template>
    <el-tabs v-model="activeName">
      <el-tab-pane :label="$t('views.model.modelForm.title.baseInfo')" name="base-info">
        <DynamicsForm
          :key="paramsRevision"
          v-model="form_data"
          :render_data="model_form_field"
          :model="form_data"
          ref="dynamicsFormRef"
          label-position="top"
          require-asterisk-position="right"
          class="mb-24"
          label-width="auto"
        >
          <template #default>
            <el-form-item prop="name" :rules="base_form_data_rule.name">
              <template #label>
                <div class="flex align-center" style="display: inline-flex">
                  <div class="mr-4">
                    <span> {{ $t('views.model.modelForm.modeName.label') }} </span>
                  </div>
                  <el-tooltip effect="dark" placement="right">
                    <template #content>
                      <p>{{ $t('views.model.modelForm.modeName.tooltip') }}</p>
                    </template>
                    <AppIcon iconName="app-warning" class="app-warning-icon"></AppIcon>
                  </el-tooltip>
                </div>
              </template>
              <el-input
                v-model="base_form_data.name"
                maxlength="64"
                show-word-limit
                :placeholder="$t('views.model.modelForm.modeName.placeholder')"
              />
            </el-form-item>
            <el-form-item prop="model_type" :rules="base_form_data_rule.model_type">
              <template #label>
                <div class="flex align-center" style="display: inline-flex">
                  <span class="mr-4">{{ $t('views.model.modelForm.model_type.label') }} </span>
                  <el-tooltip effect="dark" placement="right">
                    <template #content>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip1') }}</p>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip2') }}</p>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip3') }}</p>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip4') }}</p>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip5') }}</p>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip6') }}</p>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip7') }}</p>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip8') }}</p>
                      <p>{{ $t('views.model.modelForm.model_type.tooltip9') }}</p>
                    </template>
                    <AppIcon iconName="app-warning" class="app-warning-icon"></AppIcon>
                  </el-tooltip>
                </div>
              </template>
              <el-select
                v-loading="model_type_loading"
                @change="list_base_model"
                v-model="base_form_data.model_type"
                class="w-full m-2"
                :placeholder="$t('views.model.modelForm.model_type.placeholder')"
              >
                <el-option
                  v-for="item in model_type_list"
                  :key="item.value"
                  :label="item.key"
                  :value="item.value"
                ></el-option>
              </el-select>
            </el-form-item>

            <el-form-item prop="model_name" :rules="base_form_data_rule.model_name">
              <template #label>
                <div class="flex align-center" style="display: inline-flex">
                  <div class="mr-4">
                    <span>{{ $t('views.model.modelForm.base_model.label') }} </span>
                    <span class="color-danger ml-4">{{
                      $t('views.model.modelForm.base_model.tooltip')
                    }}</span>
                  </div>
                </div>
              </template>
              <el-select
                @change="getModelForm($event)"
                v-loading="base_model_loading"
                v-model="base_form_data.model_name"
                class="w-full m-2"
                :placeholder="$t('views.model.modelForm.base_model.placeholder')"
                filterable
                allow-create
                default-first-option
              >
                <el-option v-for="item in base_model_list" :key="item.name" :value="item.name">
                  <template #default>
                    <div class="flex align-center" style="display: inline-flex">
                      <div class="flex-between mr-4">
                        <span>{{ item.name }} </span>
                        <small v-if="item.status === 'deprecated' || item.status === 'legacy'">
                          {{ $t('views.model.lifecycle.' + item.status) }}
                        </small>
                      </div>
                      <el-tooltip effect="dark" placement="right" v-if="item.desc">
                        <template #content>
                          <p class="w-280">{{ item.desc }}</p>
                        </template>
                        <AppIcon iconName="app-warning" class="app-warning-icon"></AppIcon>
                      </el-tooltip>
                    </div>
                  </template>
                </el-option>
              </el-select>
              <div v-if="selectedModel" class="model-reference">
                <span>{{ selectedModel.desc }}</span>
                <a
                  v-if="selectedModel.docs_url"
                  :href="selectedModel.docs_url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ $t('views.model.officialDocs') }} ↗
                </a>
              </div>
              <el-button
                v-if="configFailed"
                link
                type="primary"
                @click="getModelForm(base_form_data.model_name)"
              >
                {{ $t('views.model.retryDefaults') }}
              </el-button>
            </el-form-item>
          </template>
        </DynamicsForm>
      </el-tab-pane>
      <el-tab-pane :label="$t('views.model.modelForm.title.advancedInfo')" name="advanced-info">
        <el-empty
          v-if="!base_form_data.model_type || !base_form_data.model_name"
          :description="$t('views.model.tip.emptyMessage1')"
        />
        <template v-else>
          <DynamicsForm
            v-if="base_form_data.model_params_form.length"
            :key="paramsRevision"
            ref="paramsRef"
            v-model="paramValues"
            :render_data="base_form_data.model_params_form"
            label-position="top"
            default-item-width="100%"
          />
          <el-empty
            v-else-if="configurationReady"
            :description="$t('views.model.tip.emptyMessage2')"
          />
          <details
            :open="editSchema"
            @toggle="editSchema = ($event.target as HTMLDetailsElement).open"
          >
            <summary>{{ $t('views.model.editSchema') }}</summary>
            <div class="flex-between mb-8">
              <h5>{{ $t('views.model.modelForm.title.modelParams') }}</h5>
              <el-button type="text" @click.stop="openAddDrawer()" :disabled="!configurationReady">
                <AppIcon iconName="app-add-outlined" class="mr-4" /> {{ $t('common.add') }}
              </el-button>
            </div>
            <el-table
              :data="base_form_data.model_params_form"
              v-if="base_form_data.model_params_form.length"
              class="mb-16"
            >
              <el-table-column
                prop="label"
                :label="$t('dynamicsForm.paramForm.name.label')"
                show-overflow-tooltip
              >
                <template #default="{ row }">
                  <span v-if="row.label && row.label.input_type === 'TooltipLabel'">{{
                    row.label.label
                  }}</span>
                  <span v-else>{{ row.label }}</span>
                </template>
              </el-table-column>
              <el-table-column
                prop="field"
                :label="$t('dynamicsForm.paramForm.field.label')"
                show-overflow-tooltip
                width="95px"
              />
              <el-table-column :label="$t('dynamicsForm.paramForm.input_type.label')" width="110px">
                <template #default="{ row }">
                  <el-tag size="small" type="info" class="info-tag">{{
                    input_type_list.find((item) => item.value === row.input_type)?.label
                  }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column
                prop="default_value"
                :label="$t('dynamicsForm.default.label')"
                show-overflow-tooltip
              />
              <el-table-column :label="$t('common.required')">
                <template #default="{ row }">
                  <div @click.stop>
                    <el-switch disabled size="small" v-model="row.required" />
                  </div>
                </template>
              </el-table-column>

              <el-table-column :label="$t('common.operation')" align="left" width="90">
                <template #default="{ row, $index }">
                  <span class="mr-4">
                    <el-tooltip effect="dark" :content="$t('common.modify')" placement="top">
                      <el-button type="primary" text @click.stop="openAddDrawer(row, $index)">
                        <AppIcon iconName="app-edit"></AppIcon>
                      </el-button>
                    </el-tooltip>
                  </span>
                  <el-tooltip effect="dark" :content="$t('common.delete')" placement="top">
                    <el-button type="primary" text @click="deleteParam($index)">
                      <AppIcon iconName="app-delete"></AppIcon>
                    </el-button>
                  </el-tooltip>
                </template>
              </el-table-column>
            </el-table>
          </details>
        </template>
      </el-tab-pane>
    </el-tabs>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="close">{{ $t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          @click="submit"
          :disabled="!configurationReady"
          :loading="loading"
        >
          {{ $t('common.save') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
  <AddParamDrawer ref="AddParamRef" @refresh="refresh" />
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import type { Provider, BaseModel } from '@/api/type/model'
import type { Dict, KeyValue } from '@/api/type/common'
import ProviderApi from '@/api/model/provider'
import type { FormField } from '@/components/dynamics-form/type'
import DynamicsForm from '@/components/dynamics-form/index.vue'
import AddParamDrawer from '@/views/model/component/AddParamDrawer.vue'
import { input_type_list } from '@/components/dynamics-form/constructor/data'
import type { FormRules } from 'element-plus'
import { MsgError, MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import useStore from '@/stores'

const route = useRoute()
const { user } = useStore()

const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})
const providerValue = ref<Provider>()
const dynamicsFormRef = ref<InstanceType<typeof DynamicsForm>>()
const emit = defineEmits(['change', 'submit'])
const loading = ref<boolean>(false)
const model_type_loading = ref<boolean>(false)
const base_model_loading = ref<boolean>(false)
const model_type_list = ref<Array<KeyValue<string, string>>>([])

const base_model_list = ref<Array<BaseModel>>()
const model_form_field = ref<Array<FormField>>([])
const dialogVisible = ref<boolean>(false)
const activeName = ref('base-info')
const AddParamRef = ref()
const paramsRef = ref<InstanceType<typeof DynamicsForm>>()
const paramValues = ref<Dict<any>>({})
const paramsRevision = ref(0)
const configurationReady = ref(false)
const configFailed = ref(false)
const editSchema = ref(false)
const selectedModel = computed(() =>
  base_model_list.value?.find((m) => m.name === base_form_data.value.model_name),
)
let requestId = 0
let automaticName = ''

const base_form_data_rule = ref<FormRules>({
  name: {
    required: true,
    trigger: 'blur',
    message: t('views.model.modelForm.modeName.requiredMessage'),
  },
  model_type: {
    required: true,
    trigger: 'change',
    message: t('views.model.modelForm.model_type.requiredMessage'),
  },
  model_name: {
    required: true,
    trigger: 'change',
    message: t('views.model.modelForm.base_model.requiredMessage'),
  },
})

const base_form_data = ref<{
  name: string
  model_type: string
  model_name: string
  model_params_form: FormField[]
}>({ name: '', model_type: '', model_name: '', model_params_form: [] })

const credential_form_data = ref<Dict<any>>({})

const form_data = computed({
  get: () => {
    return {
      ...credential_form_data.value,
      name: base_form_data.value.name,
      model_type: base_form_data.value.model_type,
      model_name: base_form_data.value.model_name,
      model_params_form: base_form_data.value.model_params_form,
    }
  },
  set: (event: any) => {
    credential_form_data.value = event
  },
})

const getModelForm = async (modelName: string) => {
  const provider = providerValue.value?.provider
  const type = base_form_data.value.model_type
  if (!provider || !type || !modelName) return
  const id = ++requestId
  configurationReady.value = false
  configFailed.value = false
  base_model_loading.value = true
  if (!base_form_data.value.name || base_form_data.value.name === automaticName) {
    automaticName = modelName.slice(0, 64)
    base_form_data.value.name = automaticName
  }
  try {
    const [credentials, parameters] = await Promise.all([
      ProviderApi.getModelCreateForm(provider, type, modelName),
      ProviderApi.listBaseModelParamsForm(provider, type, modelName),
    ])
    if (id !== requestId) return
    const previous = new Map(model_form_field.value.map((f) => [f.field, f.default_value]))
    const next: Dict<any> = {}
    for (const field of credentials.data) {
      // Keep values for matching fields. A different protocol gets its own endpoint default.
      if (
        previous.has(field.field) &&
        previous.get(field.field) === field.default_value &&
        credential_form_data.value[field.field] != null
      ) {
        next[field.field] = credential_form_data.value[field.field]
      } else if (field.default_value != null) {
        next[field.field] = field.default_value
      }
    }
    credential_form_data.value = next
    model_form_field.value = credentials.data
    base_form_data.value.model_params_form = parameters.data
    paramValues.value = Object.fromEntries(parameters.data.map((f) => [f.field, f.default_value]))
    paramsRevision.value++
    configurationReady.value = true
  } catch {
    if (id === requestId) configFailed.value = true
  } finally {
    if (id === requestId) base_model_loading.value = false
  }
}

const open = async (provider: Provider, modelType?: string) => {
  close()
  providerValue.value = provider
  dialogVisible.value = true
  activeName.value = 'base-info'
  const id = ++requestId
  model_type_loading.value = true
  try {
    const { data } = await ProviderApi.listModelType(provider.provider)
    if (id !== requestId) return
    model_type_list.value = data
    const first =
      data.find((t) => t.value === modelType) ?? data.find((t) => t.value === 'LLM') ?? data[0]
    if (first) await list_base_model(first.value)
  } finally {
    if (id === requestId) model_type_loading.value = false
  }
}

const list_base_model = async (type: string) => {
  const provider = providerValue.value?.provider
  if (!provider) return
  const id = ++requestId
  model_type_loading.value = false
  base_model_loading.value = true
  configurationReady.value = false
  configFailed.value = false
  base_form_data.value.model_type = type
  base_form_data.value.model_name = ''
  base_form_data.value.model_params_form = []
  paramValues.value = {}
  base_model_list.value = []
  try {
    const { data } = await ProviderApi.listBaseModel(provider, type)
    if (id !== requestId) return
    base_model_list.value = data
    if (data.length) {
      const selected = data.find((model) => model.is_default) ?? data[0]
      base_form_data.value.model_name = selected.name
      await getModelForm(selected.name)
    }
  } finally {
    if (id === requestId) base_model_loading.value = false
  }
}

const close = () => {
  ++requestId
  base_form_data.value = { name: '', model_type: '', model_name: '', model_params_form: [] }
  credential_form_data.value = {}
  model_form_field.value = []
  model_type_list.value = []
  base_model_list.value = []
  automaticName = ''
  model_type_loading.value = base_model_loading.value = loading.value = false
  configurationReady.value = configFailed.value = editSchema.value = false
  paramValues.value = {}
  providerValue.value = undefined
  dialogVisible.value = false
}

const submit = async () => {
  if (!configurationReady.value || !providerValue.value || loading.value) return
  try {
    await dynamicsFormRef.value?.validate()
  } catch {
    activeName.value = 'base-info'
    return
  }
  try {
    await paramsRef.value?.validate()
  } catch {
    activeName.value = 'advanced-info'
    return
  }
  const model_params_form = base_form_data.value.model_params_form.map((f) => ({
    ...f,
    default_value: paramValues.value[f.field] ?? f.default_value,
  }))
  const credential = Object.fromEntries(
    model_form_field.value.map((f) => [f.field, credential_form_data.value[f.field]]),
  )
  await loadSharedApi({ type: 'model', systemType: apiType.value }).createModel(
    {
      ...base_form_data.value,
      model_params_form,
      credential,
      provider: providerValue.value.provider,
    },
    loading,
  )
  close()
  MsgSuccess(t('views.model.tip.createSuccessMessage'))
  emit('submit')
  await user.profile()
}

function openAddDrawer(data?: any, index?: any) {
  AddParamRef.value?.open(
    data
      ? { ...data, default_value: paramValues.value[data.field] ?? data.default_value }
      : undefined,
    index,
  )
}

function deleteParam(index: any) {
  const [removed] = base_form_data.value.model_params_form.splice(index, 1)
  delete paramValues.value[removed.field]
  paramsRevision.value++
}

function refresh(data: any, index: any) {
  for (let i = 0; i < base_form_data.value.model_params_form.length; i++) {
    const field = base_form_data.value.model_params_form[i].field
    let label = base_form_data.value.model_params_form[i].label
    if (label && label.input_type === 'TooltipLabel') {
      label = label.label
    }
    let label2 = data.label
    if (label2 && label2.input_type === 'TooltipLabel') {
      label2 = label2.label
    }

    if (field === data.field && index !== i) {
      MsgError(t('views.model.tip.errorMessage') + data.field)
      return
    }
    if (label === label2 && index !== i) {
      MsgError(t('views.model.tip.errorMessage') + label)
      return
    }
  }
  if (index != null) {
    delete paramValues.value[base_form_data.value.model_params_form[index].field]
    base_form_data.value.model_params_form.splice(index, 1, data)
  } else {
    base_form_data.value.model_params_form.push(data)
  }
  paramValues.value[data.field] = data.default_value
  paramsRevision.value++
}

const toSelectProvider = () => {
  close()
  emit('change')
}
defineExpose({ open, close })
</script>
<style lang="scss" scoped>
.select-provider {
  appearance: none;
  background: none;
  border: 0;
  padding: 0;
  font-size: 16px;
  color: rgba(100, 106, 115, 1);
  font-weight: 400;
  line-height: 24px;
  cursor: pointer;

  &:hover {
    color: var(--el-color-primary);
  }
}
.model-reference {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.model-reference a,
summary {
  color: var(--el-color-primary);
}
summary {
  cursor: pointer;
  padding-block: 12px;
}

.active-breadcrumb {
  font-size: 16px;
  color: var(--el-text-color-primary);
  font-weight: 500;
  line-height: 24px;
}
</style>
