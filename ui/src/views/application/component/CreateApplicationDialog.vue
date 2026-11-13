<template>
  <el-dialog
    :title="$t('views.application.createAgent')"
    class="agent-create-dialog"
    v-model="dialogVisible"
    width="min(640px, calc(100vw - 24px))"
    align-center
    :show-close="!loading"
    append-to-body
    :close-on-click-modal="false"
    :close-on-press-escape="!loading"
  >
    <el-form
      ref="applicationFormRef"
      :model="applicationForm"
      :rules="rules"
      label-position="top"
      require-asterisk-position="right"
      :disabled="loading"
      @submit.prevent="submitHandle(applicationFormRef)"
    >
      <fieldset v-if="!work_flow_template" class="choice-group agent-type-choice">
        <legend>{{ $t('common.type') }}</legend>
        <div class="choice-grid">
          <label class="choice" v-for="option in agentTypes" :key="option.value">
            <input type="radio" name="agent-type" v-model="applicationForm.type" :value="option.value" :disabled="loading" />
            <span class="choice-copy">
              <strong>{{ $t(option.label) }}</strong>
              <small>{{ $t(option.description) }}</small>
            </span>
          </label>
        </div>
      </fieldset>
      <el-form-item :label="$t('common.name')" prop="name">
        <el-input
          v-model="applicationForm.name"
          maxlength="64"
          :placeholder="$t('views.application.form.appName.placeholder')"
          show-word-limit
          @blur="applicationForm.name = applicationForm.name?.trim()"
        />
      </el-form-item>
      <el-form-item :label="$t('common.desc')">
        <el-input
          v-model="applicationForm.desc"
          type="textarea"
          :placeholder="$t('views.application.form.appDescription.placeholder')"
          :rows="3"
          maxlength="256"
          show-word-limit
        />
      </el-form-item>

      <fieldset v-if="applicationForm.type === 'WORK_FLOW' && !work_flow_template" class="choice-group template-choice">
        <legend>{{ $t('views.document.upload.template') }}</legend>
        <div class="choice-grid">
          <label class="choice" v-for="option in templates" :key="option.value">
            <input type="radio" name="agent-template" v-model="appTemplate" :value="option.value" :disabled="loading" />
            <span>{{ $t(option.label) }}</span>
          </label>
        </div>
        <p v-if="appTemplate === 'assistant'" class="choice-hint">{{ $t('views.application.form.appTemplate.assistantApp.description') }}</p>
      </fieldset>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click.prevent="dialogVisible = false" :disabled="loading">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button type="primary" @click="submitHandle(applicationFormRef)" :loading="loading">
          {{ $t('common.create') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import type { ApplicationFormType } from '@/api/type/application'
import type { FormInstance, FormRules } from 'element-plus'
import applicationApi from '@/api/application/application'
import { MsgSuccess } from '@/utils/message'
import { isWorkFlow } from '@/utils/application'
import { cloneDeep } from 'lodash'
import { applicationTemplate } from '@/workflow/common/template'
import { t } from '@/locales'
import useStore from '@/stores'
const { user } = useStore()
const router = useRouter()
const emit = defineEmits(['refresh'])

const defaultPrompt = t('views.application.form.prompt.defaultPrompt', {
  data: '{data}',
  question: '{question}',
})

const optimizationPrompt =
  t('views.application.dialog.defaultPrompt1', {
    question: '{question}',
  }) +
  '<data></data>' +
  t('views.application.dialog.defaultPrompt2')

const agentTypes = [
  { value: 'SIMPLE', label: 'views.application.simpleAgent', description: 'views.application.simpleBrief' },
  { value: 'WORK_FLOW', label: 'views.application.workflowAgent', description: 'views.application.workflowBrief' },
]
const templates = [
  { value: 'blank', label: 'views.application.form.appTemplate.blankApp.title' },
  { value: 'assistant', label: 'views.application.form.appTemplate.assistantApp.title' },
]
const appTemplate = ref('blank')

const applicationFormRef = ref()

const loading = ref(false)
const dialogVisible = ref<boolean>(false)
const work_flow_template = ref()

function newForm(type = 'SIMPLE'): ApplicationFormType {
  return {
    name: '',
    desc: '',
    model_id: undefined,
    dialogue_number: 1,
    prologue: t('views.application.form.defaultPrologue'),
    knowledge_id_list: [],
    knowledge_setting: {
      top_n: 3,
      similarity: 0.6,
      max_paragraph_char_number: 5000,
      search_mode: 'embedding',
      no_references_setting: {
        status: 'ai_questioning',
        value: '{question}',
      },
    },
    model_setting: {
      prompt: defaultPrompt,
      system: '',
      no_references_prompt: '{question}',
    },
    model_params_setting: {},
    problem_optimization: false,
    problem_optimization_prompt: optimizationPrompt,
    stt_model_id: undefined,
    tts_model_id: undefined,
    stt_model_enable: false,
    tts_model_enable: false,
    tts_type: 'BROWSER',
    type,
  }
}
const applicationForm = ref<ApplicationFormType>(newForm())

const rules = reactive<FormRules<ApplicationFormType>>({
  name: [
    {
      required: true,
      message: t('views.application.form.appName.placeholder'),
      trigger: 'blur',
    },
  ],
  model_id: [
    {
      required: false,
      message: t('views.application.form.aiModel.placeholder'),
      trigger: 'change',
    },
  ],
})

const currentFolder = ref('')

const open = (folder: string, type?: string, work_flow?: any) => {
  currentFolder.value = folder
  appTemplate.value = 'blank'
  applicationForm.value = newForm(type)
  work_flow_template.value = work_flow
  applicationFormRef.value?.clearValidate()
  dialogVisible.value = true
}

const submitHandle = async (formEl: FormInstance | undefined) => {
  if (!formEl || loading.value) return
  loading.value = true
  try {
    if (!(await formEl.validate().catch(() => false))) return
    const payload = { ...applicationForm.value, folder_id: currentFolder.value }
    if (isWorkFlow(payload.type)) {
      const graph = cloneDeep(applicationTemplate[appTemplate.value])
      Object.assign(graph.nodes[0].properties.node_data, { name: payload.name, desc: payload.desc })
      payload.work_flow = graph
      if (work_flow_template.value) payload.work_flow_template = work_flow_template.value
    }
    const { data } = await applicationApi.postApplication(payload)
    dialogVisible.value = false
    emit('refresh')
    MsgSuccess(t('common.createSuccess'))
    await user.profile()
    const next = isWorkFlow(payload.type) ? 'workflow' : `${data.type}/setting`
    await router.push(`/application/workspace/${data.id}/${next}`)
  } finally {
    loading.value = false
  }
}

defineExpose({ open })
</script>
<style lang="scss" scoped>
.choice-group { min-width: 0; margin: 0 0 18px; padding: 0; border: 0; }
.choice-group legend { margin-bottom: 8px; padding: 0; font-size: 14px; font-weight: 550; }
.choice-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.choice {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 13px; border: 1px solid var(--studio-hairline);
  border-radius: 12px; background: var(--app-view-bg-color); cursor: pointer;
  &:has(input:checked) { border-color: var(--studio-ink); background: var(--studio-selection); }
  &:has(input:focus-visible) { outline: 2px solid var(--studio-ink); outline-offset: 2px; }
  input { flex: none; width: 16px; height: 16px; margin: 2px 0 0; accent-color: var(--studio-ink); }
  input:focus-visible { outline: none !important; }
}
.choice-copy { display: grid; gap: 4px; line-height: 1.4; }
.choice-copy strong { font-size: 14px; color: var(--studio-ink); }
.choice-copy small, .choice-hint { color: var(--app-text-color-secondary); font-size: 12px; }
.choice-hint { margin: 8px 0 0; }
.template-choice { margin-bottom: 0; }
.template-choice .choice { padding-block: 10px; align-items: center; }
@media (max-width: 540px) {
  .agent-type-choice .choice-grid { grid-template-columns: 1fr; }
  .choice { padding: 10px 12px; }
  .choice-copy { gap: 2px; }
}
</style>
