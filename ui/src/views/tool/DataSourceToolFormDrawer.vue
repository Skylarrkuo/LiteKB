<template>
  <el-drawer
    class="tool-editor-drawer tool-editor-datasource"
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
                message: $t('views.tool.form.toolName.requiredMessage'),
                trigger: 'blur',
              },
            ]"
          >
            <el-input
              v-model="form.name"
              :placeholder="$t('views.tool.form.toolName.placeholder')"
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
      </el-form>
      <ToolParameterList kind="init" v-model:rows="form.init_field_list" :editable="canSave" />
      <ToolParameterList
        kind="input"
        v-model:rows="form.input_field_list"
        :editable="canSave"
        :hint="$t('views.tool.form.param.paramInfo1')"
      />
      <section class="tool-form-section">
        <div class="tool-section-heading">
          <div>
            <h3>
              {{ $t('views.tool.form.param.code') }}
              <span class="tool-required" aria-hidden="true">*</span>
            </h3>
            <p>{{ $t('views.tool.form.param.paramInfo2') }}</p>
          </div>
        </div>
        <div class="tool-code-field" ref="codeField">
          <CodemirrorEditor
            v-if="visible"
            v-model="form.code"
            :title="$t('views.tool.form.param.code')"
            :autofocus="false"
            @submitDialog="form.code = $event"
          />
        </div>
        <p v-if="showCodeError && !form.code?.trim()" class="tool-form-error" role="alert">
          {{ $t('views.tool.editor.codeRequired') }}
        </p>
      </section>
    </div>
    <template #footer>
      <div class="tool-editor-actions">
        <el-button :disabled="loading" @click="close">{{ $t('common.cancel') }}</el-button>
        <el-button v-if="canSave" type="primary" :loading="loading" @click="save(checkCode)">
          {{ $t(isEdit ? 'common.save' : 'common.create') }}
        </el-button>
      </div>
    </template>
    <EditAvatarDialog ref="avatarEditor" iconType="DATA_SOURCE" @refresh="form.icon = $event" />
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import toolIcon from '@/assets/tool/icon_datasource.svg'
import ToolEditorHeading from './component/ToolEditorHeading.vue'
import EditAvatarDialog from './component/EditAvatarDialog.vue'
import { useToolEditor } from './useToolEditor'
import ToolParameterList from './component/ToolParameterList.vue'

defineProps<{ title?: string }>()
const emit = defineEmits(['refresh', 'created'])
const avatarEditor = ref<InstanceType<typeof EditAvatarDialog>>()
const codeTemplate = `
def get_form_list(node, **kwargs):
    """
    获取表单配置列表

    Args:
        node: 节点对象
        **kwargs: 其他关键字参数

    Returns:
        list: 包含表单字段配置的列表，用于构建文件树选择器
    """
    return [{
        "field": 'file_list',
        "text_field": 'name',
        "value_field": 'token',
        "input_type": 'Tree',
        "attrs": {
            "lazy": True,
            "fetch_list_function": "get_file_list",
        },
        "label": '',
    }]

def get_file_list(app_id=None, app_secret=None, folder_token=None, **kwargs):
    """
    获取文件列表

    Args:
        app_id (str, optional): 应用ID
        app_secret (str, optional): 应用密钥
        folder_token (str, optional): 文件夹token
        **kwargs: 其他关键字参数，包括current_node当前节点信息

    Returns:
        list: 过滤后的文件列表，每个文件包含leaf标识和原始文件信息
    """
    pass

def get_down_file_list(app_id=None, app_secret=None, **kwargs):
    """
    获取需要下载的文件列表（过滤掉文件夹）

    Args:
        app_id (str, optional): 应用ID
        app_secret (str, optional): 应用密钥
        **kwargs: 其他关键字参数，包括file_list文件列表

    Returns:
        list: 过滤后的文件列表，不包含文件夹类型
    """
    pass

def download(app_id=None, app_secret=None, **kwargs):
    """
    下载文件

    支持下载文档(docx)、表格(sheet)和普通文件
    - 对于文档和表格，先创建导出任务，轮询等待导出完成后下载
    - 对于普通文件，直接下载

    Args:
        app_id (str, optional): 应用ID
        app_secret (str, optional): 应用密钥
        **kwargs: 其他关键字参数，包括download_item下载项信息

    Returns:
        dict: 包含文件字节数组(base64编码)和文件名的字典
              {'file_bytes': [base64_chunk1, base64_chunk2, ...], 'name': 'filename.ext'}

    Raises:
        Exception: 当创建导出任务失败、查询任务失败或导出任务超时时抛出异常
    """
    pass
`

const {
  form,
  visible,
  loading,
  isEdit,
  canSave,
  FormRef,
  open: openEditor,
  close,
  save,
} = useToolEditor(
  () => ({
    name: '',
    desc: '',
    icon: '',
    code: codeTemplate,
    init_field_list: [],
    input_field_list: [],
    tool_type: 'DATA_SOURCE',
  }),
  (data, created) => {
    emit('refresh', data)
    if (created) emit('created', data)
  },
)
const codeField = ref<HTMLElement>()
const showCodeError = ref(false)
function checkCode() {
  showCodeError.value = !form.value.code?.trim()
  if (showCodeError.value) codeField.value?.querySelector<HTMLElement>('.cm-content')?.focus()
  return !showCodeError.value
}
function open(data?: Parameters<typeof openEditor>[0]) {
  showCodeError.value = false
  openEditor(data)
}

defineExpose({ open })
</script>
