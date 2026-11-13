<template>
  <el-dialog
    class="tool-editor-dialog tool-workflow-dialog"
    :title="title"
    v-model="dialogVisible"
    width="540px"
    align-center
    append-to-body
    :close-on-click-modal="false"
    :show-close="!loading"
    :close-on-press-escape="!loading"
    destroy-on-close
  >
    <template #header="{ titleId }">
      <ToolEditorHeading
        :title="title"
        :title-id="titleId"
        :fallback="toolIcon"
        :icon="form.icon"
        :editable="!!form.id"
        @edit-icon="avatarEditor?.open(form)"
      />
    </template>
    <el-form
      ref="formRef"
      :model="form"
      label-position="top"
      require-asterisk-position="right"
      :disabled="loading"
      @submit.prevent="save"
    >
      <el-form-item
        :label="$t('views.tool.form.workflowName.label')"
        prop="name"
        :rules="[
          {
            required: true,
            whitespace: true,
            message: $t('views.tool.form.workflowName.requiredMessage'),
            trigger: 'blur',
          },
        ]"
      >
        <el-input
          v-model="form.name"
          :placeholder="$t('views.tool.form.workflowName.placeholder')"
          maxlength="64"
          show-word-limit
          @blur="form.name = form.name?.trim()"
        />
      </el-form-item>
      <el-form-item :label="$t('common.desc')">
        <el-input
          v-model="form.desc"
          type="textarea"
          :placeholder="$t('common.descPlaceholder')"
          maxlength="128"
          show-word-limit
          :autosize="{ minRows: 3, maxRows: 6 }"
          @blur="form.desc = form.desc?.trim()"
        />
      </el-form-item>
      <button class="tool-submit-key" type="submit" tabindex="-1" aria-hidden="true"></button>
    </el-form>
    <template #footer>
      <div class="tool-editor-actions">
        <el-button :disabled="loading" @click="dialogVisible = false">{{
          $t('common.cancel')
        }}</el-button>
        <el-button type="primary" @click="save" :loading="loading">{{
          $t(form.id ? 'common.save' : 'common.create')
        }}</el-button>
      </div>
    </template>
    <EditAvatarDialog ref="avatarEditor" @refresh="form.icon = $event" iconType="WORKFLOW" />
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance } from 'element-plus'
import { cloneDeep } from 'lodash'
import type { toolData } from '@/api/type/tool'
import EditAvatarDialog from './component/EditAvatarDialog.vue'
import ToolEditorHeading from './component/ToolEditorHeading.vue'
import toolIcon from '@/assets/workflow/logo_workflow.svg'
import { MsgSuccess } from '@/utils/message'
import { t } from '@/locales'
import useStore from '@/stores'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'

defineProps<{ title?: string }>()
const emit = defineEmits(['refresh'])
const route = useRoute()
const router = useRouter()
const { user, folder } = useStore()
const formRef = ref<FormInstance>()
const avatarEditor = ref<InstanceType<typeof EditAvatarDialog>>()
const dialogVisible = ref(false)
const loading = ref(false)
const newWorkflow = () => ({ name: '', desc: '', tool_type: 'WORKFLOW', work_flow: {} })
const form = ref<toolData & { work_flow?: object }>(newWorkflow())
const apiType = computed(() => {
  if (route.path.includes('shared')) return 'systemShare'
  if (route.path.includes('resource-management')) return 'systemManage'
  return 'workspace'
})

function open(data?: toolData) {
  form.value = { ...newWorkflow(), ...cloneDeep(data) }
  dialogVisible.value = true
}
async function save() {
  if (loading.value || !formRef.value) return
  loading.value = true
  try {
    form.value.name = form.value.name?.trim()
    if (!(await formRef.value.validate().catch(() => false))) return
    const api = loadSharedApi({ type: 'tool', systemType: apiType.value })
    if (form.value.id) {
      const { name, desc, icon } = form.value
      const { data } = await api.putTool(form.value.id, { name, desc, icon })
      MsgSuccess(t('common.editSuccess'))
      dialogVisible.value = false
      emit('refresh', data)
      await user.profile()
    } else {
      const { data } = await api.postTool({
        ...form.value,
        folder_id: folder.currentFolder?.id || user.getWorkspaceId() || 'default',
        code: 'None',
      })
      MsgSuccess(t('common.createSuccess'))
      dialogVisible.value = false
      emit('refresh', data)
      await user.profile()
      const folderId = data.scope === 'SHARED' ? 'shared' : data.folder_id
      await router.push({ name: 'ToolWorkflow', params: { id: data.id, folderId } })
    }
  } finally {
    loading.value = false
  }
}
defineExpose({ open })
</script>
