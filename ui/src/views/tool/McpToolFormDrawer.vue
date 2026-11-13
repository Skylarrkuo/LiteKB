<template>
  <el-drawer
    class="tool-editor-drawer tool-editor-mcp"
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
                message: $t('views.tool.form.mcpName.requiredMessage'),
                trigger: 'blur',
              },
            ]"
          >
            <el-input
              v-model="form.name"
              :placeholder="$t('views.tool.form.mcpName.placeholder')"
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
        <section class="tool-form-section">
          <h3>{{ $t('views.tool.mcp.title') }}</h3>
          <el-form-item
            prop="code"
            :rules="[{ validator: validateJson, trigger: 'blur' }]"
            :label="$t('views.tool.mcp.label')"
          >
            <el-input
              class="tool-json"
              v-model="form.code"
              :placeholder="mcpServerJson"
              type="textarea"
              :autosize="{ minRows: 6, maxRows: 16 }"
              spellcheck="false"
            />
            <p class="tool-field-hint">{{ $t('views.tool.mcp.tip') }}</p>
          </el-form-item>
        </section>
      </el-form>
    </div>
    <template #footer>
      <div class="tool-editor-actions">
        <el-button
          class="tool-secondary-action"
          :loading="testing"
          :disabled="loading"
          @click="testConnection"
        >
          {{ $t('views.system.test') }}
        </el-button>
        <el-button :disabled="loading" @click="close">{{ $t('common.cancel') }}</el-button>
        <el-button
          v-if="canSave"
          type="primary"
          :loading="loading"
          :disabled="testing"
          @click="save()"
        >
          {{ $t(isEdit ? 'common.save' : 'common.create') }}
        </el-button>
      </div>
    </template>
    <EditAvatarDialog ref="avatarEditor" iconType="MCP" @refresh="form.icon = $event" />
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { t } from '@/locales'
import toolIcon from '@/assets/tool/icon_mcp.svg'
import ToolEditorHeading from './component/ToolEditorHeading.vue'
import EditAvatarDialog from './component/EditAvatarDialog.vue'
import { useToolEditor } from './useToolEditor'

import { MsgSuccess } from '@/utils/message'
defineProps<{ title?: string }>()
const emit = defineEmits(['refresh', 'created'])
const avatarEditor = ref<InstanceType<typeof EditAvatarDialog>>()

const { form, visible, loading, isEdit, canSave, FormRef, api, open, close, save } = useToolEditor(
  () => ({
    name: '',
    desc: '',
    icon: '',
    code: '',
    init_field_list: [],
    input_field_list: [],
    tool_type: 'MCP',
  }),
  (data, created) => {
    emit('refresh', data)
    if (created) emit('created', data)
  },
)

const testing = ref(false)
const mcpServerJson = JSON.stringify(
  { math: { url: 'https://example.com/mcp', transport: 'streamable_http' } },
  null,
  2,
)
function validateJson(_rule: unknown, value: string, done: (error?: Error) => void) {
  if (!value?.trim()) return done(new Error(t('views.tool.mcp.requiredMessage')))
  try {
    const parsed = JSON.parse(value)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return done()
  } catch {
    // The field shows the same error for syntax and top-level shape.
  }
  done(new Error(t('workflow.nodes.mcpNode.mcpServerTip')))
}
async function testConnection() {
  if (testing.value || loading.value) return
  testing.value = true
  try {
    const valid = await FormRef.value?.validateField('code').catch(() => false)
    if (!valid) return
    await api.value.postToolTestConnection({ code: form.value.code })
    MsgSuccess(t('views.system.testSuccess'))
  } finally {
    testing.value = false
  }
}
defineExpose({ open })
</script>
