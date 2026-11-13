<template>
  <el-drawer
    class="tool-editor-drawer tool-editor-python"
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
          <el-button v-if="canSave" @click="openGenerator">
            <AppIcon iconName="app-generate-star" />{{
              $t('views.application.generateDialog.label')
            }}
          </el-button>
        </div>
        <div class="tool-code-field" ref="codeField">
          <CodemirrorEditor
            v-if="visible"
            v-model="form.code"
            :title="$t('views.tool.form.param.code')"
            :autofocus="false"
            @submitDialog="form.code = $event"
          >
            <template #header-extra>
              <el-button link type="primary" v-if="canSave" @click="openGenerator">
                {{ $t('views.application.generateDialog.label') }}
              </el-button>
            </template>
          </CodemirrorEditor>
        </div>
        <p v-if="showCodeError && !form.code?.trim()" class="tool-form-error" role="alert">
          {{ $t('views.tool.editor.codeRequired') }}
        </p>
      </section>
      <section class="tool-form-section">
        <h3>{{ $t('common.param.outputParam') }}</h3>
        <div class="tool-output">
          <span>{{ $t('common.result') }}</span
          ><code>{result}</code>
        </div>
      </section>
    </div>
    <template #footer>
      <div class="tool-editor-actions">
        <el-button
          v-if="permissions.debug()"
          class="tool-secondary-action"
          :disabled="loading"
          @click="debugDrawer?.open(form)"
          >{{ $t('common.debug') }}</el-button
        >
        <el-button :disabled="loading" @click="close">{{ $t('common.cancel') }}</el-button>
        <el-button v-if="canSave" type="primary" :loading="loading" @click="save(checkCode)">
          {{ $t(isEdit ? 'common.save' : 'common.create') }}
        </el-button>
      </div>
    </template>
    <EditAvatarDialog ref="avatarEditor" @refresh="form.icon = $event" />
    <ToolDebugDrawer ref="debugDrawer" />
    <GenerateCodeDialog ref="generator" :toolData="form" @replace="replaceCode" />
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { t } from '@/locales'
import toolIcon from '@/assets/tool/icon_tool.svg'
import ToolEditorHeading from './component/ToolEditorHeading.vue'
import EditAvatarDialog from './component/EditAvatarDialog.vue'
import { useToolEditor } from './useToolEditor'
import ToolParameterList from './component/ToolParameterList.vue'
import ToolDebugDrawer from './ToolDebugDrawer.vue'
import GenerateCodeDialog from './component/GenerateCodeDialog.vue'
import { MsgSuccess } from '@/utils/message'

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
  permissions,
  open: openEditor,
  close,
  save,
} = useToolEditor(
  () => ({ name: '', desc: '', icon: '', code: '', init_field_list: [], input_field_list: [] }),
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
const debugDrawer = ref<InstanceType<typeof ToolDebugDrawer>>()
const generator = ref<InstanceType<typeof GenerateCodeDialog>>()
function openGenerator() {
  generator.value?.open(form.value.init_field_list ?? [], form.value.input_field_list ?? [])
}
function replaceCode(code: string) {
  form.value.code = code.replace(/^```python\s*\n?/, '').replace(/\n?```\s*$/, '')
  MsgSuccess(t('views.document.tip.replaceSuccess'))
}
defineExpose({ open })
</script>
