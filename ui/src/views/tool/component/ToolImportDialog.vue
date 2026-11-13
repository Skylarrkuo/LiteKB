<template>
  <el-dialog
    v-model="visible"
    :title="t('views.tool.library.importFile')"
    width="min(460px, calc(100% - 24px))"
    :close-on-click-modal="!sending"
    :close-on-press-escape="!sending"
    :show-close="!sending"
    append-to-body
  >
    <div class="import-body">
      <div class="destination">
        <el-icon aria-hidden="true"><FolderOpened /></el-icon>
        <div>
          <span>{{ t('views.tool.library.target') }}</span
          ><strong>{{ targetName }}</strong>
        </div>
      </div>
      <div class="file-field">
        <label :for="inputId">{{ t('views.tool.library.file') }}</label>
        <input
          ref="inputRef"
          :id="inputId"
          data-testid="tool-import-file"
          class="file-input"
          type="file"
          accept=".tool"
          :disabled="sending"
          :aria-describedby="hintId"
          @change="onFile"
        />
        <span class="file-display" aria-hidden="true"
          ><el-icon><Upload /></el-icon
          ><span>{{ selected?.name || t('views.tool.library.selectFile') }}</span></span
        >
      </div>
      <p :id="hintId" class="hint">{{ t('views.tool.library.format') }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
    </div>
    <template #footer>
      <el-button :disabled="sending" @click="visible = false">{{ t('common.cancel') }}</el-button>
      <el-button
        data-testid="tool-import-submit"
        type="primary"
        :disabled="!selected"
        :loading="sending"
        @click="submit"
      >
        {{ t('views.tool.importTool') }}
      </el-button>
    </template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, useId } from 'vue'
import { FolderOpened, Upload } from '@element-plus/icons-vue'
import { t } from '@/locales'
import { MsgSuccess } from '@/utils/message'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'

const props = defineProps<{ apiType: 'workspace' | 'systemShare' | 'systemManage' }>()
const emit = defineEmits<{ imported: [tool: { id: string }] }>()
const inputId = useId()
const hintId = useId()
const visible = ref(false)
const sending = ref(false)
const selected = ref<File>()
const inputRef = ref<HTMLInputElement>()
const targetId = ref('')
const targetName = ref('')
const error = ref('')

function open(folderId: string, folderName: string) {
  if (sending.value) return
  targetId.value = folderId
  targetName.value = folderName
  selected.value = undefined
  error.value = ''
  if (inputRef.value) inputRef.value.value = ''
  visible.value = true
}
function onFile(event: Event) {
  const file = (event.currentTarget as HTMLInputElement).files?.[0]
  if (!file) return
  const valid = file.name.toLowerCase().endsWith('.tool')
  selected.value = valid ? file : undefined
  error.value = valid ? '' : t('views.tool.library.format')
}
async function submit() {
  const file = selected.value
  if (!file || sending.value) return
  sending.value = true
  error.value = ''
  const data = new FormData()
  data.append('file', file, file.name)
  data.append('folder_id', targetId.value)
  try {
    const result = await loadSharedApi({ type: 'tool', systemType: props.apiType }).postImportTool(
      data,
    )
    visible.value = false
    emit('imported', result.data)
    MsgSuccess(t('views.tool.library.succeeded', { name: result.data?.name || file.name }))
  } catch (e: unknown) {
    const failure = e as { message?: string; response?: { data?: { message?: string } } }
    error.value =
      failure?.response?.data?.message || failure?.message || t('views.tool.library.importError')
  } finally {
    sending.value = false
  }
}
defineExpose({ open })
</script>
<style scoped>
.import-body {
  display: grid;
  gap: 12px;
}
.destination {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: var(--studio-selection);
  border-radius: var(--app-border-radius-base);
  color: var(--studio-ink);
}
.destination > .el-icon {
  font-size: 20px;
  flex: none;
}
.destination span,
.destination strong {
  display: block;
  overflow-wrap: anywhere;
}
.destination span,
.hint {
  color: var(--app-text-color-secondary);
  font-size: 12px;
}
.file-field {
  position: relative;
  display: grid;
  gap: 6px;
}
.file-field label {
  font-weight: 600;
}
.file-display {
  display: flex;
  gap: 9px;
  align-items: center;
  padding: 12px 14px;
  min-width: 0;
  color: var(--studio-ink);
  background: var(--app-view-bg-color);
  border: 1px dashed var(--studio-ink);
  border-radius: var(--app-border-radius-base);
}
.file-display span {
  overflow-wrap: anywhere;
}
.file-input {
  position: absolute;
  z-index: 1;
  inset: auto 0 0;
  width: 100%;
  height: 44px;
  opacity: 0;
  cursor: pointer;
}
.file-input:focus-visible + .file-display {
  outline: 2px solid var(--studio-ink);
  outline-offset: 3px;
}
.error,
.hint {
  margin: 0;
  overflow-wrap: anywhere;
}
.error {
  color: var(--el-color-danger-dark-2);
}
</style>
