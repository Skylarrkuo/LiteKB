<template>
  <el-drawer
    class="tool-editor-drawer tool-editor-skill"
    :title="title"
    v-model="visible"
    size="min(780px, 100%)"
    :before-close="close"
    :show-close="!loading"
    destroy-on-close
  >
    <template #header="{ titleId }">
      <ToolEditorHeading
        :title="title"
        :title-id="titleId"
        :icon="form.icon"
        :fallback="toolIcon"
        :editable="isEdit && canSave"
        @edit-icon="avatarEditor?.open(form)"
      />
    </template>
    <div class="tool-editor-content">
      <el-form
        ref="FormRef"
        :model="form"
        label-position="top"
        require-asterisk-position="right"
        :disabled="loading || !canSave"
        @submit.prevent
        scroll-to-error
      >
        <section class="tool-form-section">
          <h3>{{ $t('common.info') }}</h3>
          <el-form-item
            :label="$t('common.name')"
            prop="name"
            :rules="[
              {
                required: true,
                whitespace: true,
                message: $t('views.tool.form.skillName.requiredMessage'),
                trigger: 'blur',
              },
            ]"
          >
            <el-input
              v-model="form.name"
              :placeholder="$t('views.tool.form.skillName.placeholder')"
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
              :autosize="{ minRows: 2, maxRows: 5 }"
              @blur="form.desc = form.desc?.trim()"
            />
          </el-form-item>
        </section>
        <ToolParameterList
          kind="init"
          v-model:rows="form.init_field_list"
          :editable="canSave"
          :hint="$t('views.tool.skill.initParamPlaceholder')"
        />
        <section class="tool-form-section">
          <h3>{{ $t('views.tool.skill.skillFile') }}</h3>
          <el-form-item
            prop="code"
            :rules="[{ required: true, message: $t('views.document.upload.requiredMessage') }]"
          >
            <div v-if="form.fileList?.length" class="tool-file">
              <img :src="getImgUrl(form.fileList[0].name)" alt="" width="32" height="36" />
              <div class="tool-file-name">
                <strong>{{ form.fileList[0].name }}</strong>
                <small>{{ filesize(form.fileList[0].size) || '0K' }}</small>
              </div>
              <el-upload
                v-if="canSave"
                action="#"
                :auto-upload="false"
                :show-file-list="false"
                :disabled="loading"
                accept=".zip"
                :on-change="fileHandleChange"
              >
                <el-button link type="primary">{{ $t('views.tool.skill.reUpload') }}</el-button>
              </el-upload>
              <el-button v-if="form.id && !replacedFile" link type="primary" @click="downloadZip">
                {{ $t('views.document.upload.download') }}
              </el-button>
            </div>
            <el-upload
              v-else
              class="tool-upload"
              drag
              action="#"
              :auto-upload="false"
              :show-file-list="false"
              :disabled="!canSave || loading"
              accept=".zip"
              :on-change="fileHandleChange"
            >
              <AppIcon iconName="app-upload" />
              <strong>{{ $t('views.document.upload.selectFile') }}</strong>
              <small
                >ZIP · {{ $t('views.document.upload.fileLimitSizeTip') }}
                {{ fileSizeLimit }} MB</small
              >
            </el-upload>
          </el-form-item>
        </section>
      </el-form>
    </div>
    <template #footer>
      <div class="tool-editor-actions">
        <el-button :disabled="loading" @click="close">{{ $t('common.cancel') }}</el-button>
        <el-button v-if="canSave" type="primary" :loading="loading" @click="save()">
          {{ $t(isEdit ? 'common.save' : 'common.create') }}
        </el-button>
      </div>
    </template>
    <EditAvatarDialog ref="avatarEditor" iconType="SKILL" @refresh="form.icon = $event" />
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { t } from '@/locales'
import toolIcon from '@/assets/tool/icon_skill.svg'
import ToolEditorHeading from './component/ToolEditorHeading.vue'
import EditAvatarDialog from './component/EditAvatarDialog.vue'
import { useToolEditor } from './useToolEditor'
import ToolParameterList from './component/ToolParameterList.vue'

import type { UploadFile } from 'element-plus'
import type { toolData } from '@/api/type/tool'
import { filesize, getImgUrl } from '@/utils/common'
import { MsgError } from '@/utils/message'

defineProps<{ title?: string }>()
const emit = defineEmits(['refresh', 'created'])
const avatarEditor = ref<InstanceType<typeof EditAvatarDialog>>()

const {
  form,
  visible,
  loading,
  isEdit,
  canSave,
  FormRef,
  api,
  open: openEditor,
  close,
  save,
} = useToolEditor(
  () => ({
    name: '',
    desc: '',
    icon: '',
    code: '',
    init_field_list: [],
    input_field_list: [],
    tool_type: 'SKILL',
    fileList: [],
  }),
  (data, created) => {
    emit('refresh', data)
    if (created) emit('created', data)
  },
)

const fileSizeLimit = 100
const replacedFile = ref(false)
function open(data?: toolData) {
  replacedFile.value = false
  const files = data?.fileList?.filter((item) => item?.name) || []
  openEditor(data ? { ...data, fileList: files, code: files.length ? data.code : '' } : undefined)
}
async function fileHandleChange(file: UploadFile) {
  if (!file.raw || loading.value) return
  if (!file.name.toLowerCase().endsWith('.zip'))
    return MsgError(t('views.document.upload.errorMessage2'))
  if (!file.raw.size) return MsgError(t('views.document.upload.errorMessage3'))
  if (file.raw.size > fileSizeLimit * 1024 * 1024) {
    return MsgError(t('views.document.tip.fileLimitSizeTip1') + fileSizeLimit + ' MB')
  }
  const fd = new FormData()
  fd.append('file', file.raw)
  loading.value = true
  try {
    const res = await api.value.uploadSkillFile(fd)
    form.value.code = res.data
    form.value.fileList = [{ name: file.name, size: file.raw.size }]
    replacedFile.value = true
    FormRef.value?.clearValidate('code')
  } finally {
    loading.value = false
  }
}
async function downloadZip() {
  if (!form.value.id) return
  const file = await api.value.downloadSkillFile(form.value.id)
  const url = URL.createObjectURL(new Blob([file]))
  const link = document.createElement('a')
  link.href = url
  link.download = form.value.fileList?.[0]?.name || form.value.name + '.zip'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
defineExpose({ open })
</script>
