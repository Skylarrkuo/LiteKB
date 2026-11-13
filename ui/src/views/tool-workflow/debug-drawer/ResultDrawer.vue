<template>
  <el-drawer
    v-model="visible"
    append-to-body
    destroy-on-close
    size="min(740px, 100%)"
    :title="t('views.tool.toolWorkflow.debugResult')"
  >
    <template #header="{ titleId }">
      <div class="tool-drawer-heading">
        <el-icon aria-hidden="true"><Tickets /></el-icon>
        <h2 :id="titleId">{{ t('views.tool.toolWorkflow.debugResult') }}</h2>
      </div>
    </template>
    <div class="tool-drawer-body" data-testid="workflow-debug-result">
      <div
        v-if="statusText"
        class="tool-notice"
        :class="{ failed: record?.state === 'FAILURE' }"
        role="status"
        data-testid="workflow-debug-status"
      >
        {{ statusText }}
      </div>
      <div v-if="streamError" class="tool-notice failed" role="alert">
        {{ streamError }}
        <el-button v-if="retryInput" link type="primary" @click="retryContinuation">{{
          t('views.tool.library.retry')
        }}</el-button>
      </div>
      <div v-if="recordError" class="tool-notice failed" role="alert">{{ recordError }}</div>
      <el-button
        v-if="chat.record_id && !streamBusy"
        class="refresh"
        :loading="recordBusy"
        data-testid="workflow-debug-refresh"
        @click="readRecord"
        >{{ t('views.tool.debugPanel.refreshRecord') }}</el-button
      >
      <el-tabs v-model="tab">
        <el-tab-pane :label="t('views.tool.form.debug.output')" name="output">
          <AnswerContent
            v-if="streamBusy || renderBusy || chat.answer_text_list.some((row) => row.length)"
            v-model:chat-record="chat"
            :application="presentation"
            :loading="streamBusy || renderBusy"
            type="ai-chat"
            :send-message="sendMessage"
            :chat-management="answerControls"
            :execution-is-right-panel="false"
            :selection="true"
          />
          <section
            v-if="record && record.meta && 'output' in record.meta"
            class="tool-result"
            data-testid="workflow-debug-output"
          >
            <h3>{{ t('common.param.outputParam') }}</h3>
            <pre>{{ formatOutput(record.meta.output) }}</pre>
          </section>
        </el-tab-pane>
        <el-tab-pane :label="t('common.ExecutionRecord.title')" name="details">
          <ExecutionDetailCard
            v-for="(node, index) in steps"
            :key="node.runtime_node_id || index"
            :data="node"
          />
          <p v-if="!steps.length" class="tool-hint">{{ t('runTrace.noSteps') }}</p>
        </el-tab-pane>
      </el-tabs>
    </div>
    <template #footer
      ><el-button @click="close">{{ t('views.tool.debugPanel.backToInputs') }}</el-button></template
    >
  </el-drawer>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Tickets } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'
import { ChatManagement, type chatType } from '@/api/type/application'
import AnswerContent from '@/components/ai-chat/component/answer-content/index.vue'
import ExecutionDetailCard from '@/components/execution-detail-card/index.vue'
import { t } from '@/locales'
import { randomId } from '@/utils/common'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { errorMessage, formatOutput } from '@/views/tool/component/tool-debug'
import { readWorkflowEvents, type WorkflowFrame } from './stream'

interface NodeDetail {
  index?: number
  type?: string
  is_submit?: boolean
  runtime_node_id?: string
  [key: string]: any
}
interface ToolRecord {
  state: string
  meta?: { output?: unknown; details?: Record<string, NodeDetail> }
}
type Input = Record<string, unknown>
function newChat(): chatType {
  return {
    id: randomId(),
    problem_text: '',
    answer_text: '',
    answer_text_list: [[]],
    buffer: [],
    execution_details: [],
    write_ed: false,
    is_stop: false,
    record_id: '',
    chat_id: '',
    vote_status: '-1',
  }
}
const route = useRoute()
const api = computed(() =>
  loadSharedApi({
    type: 'tool',
    isShared: route.params.folderId === 'share',
    systemType: route.path.includes('shared')
      ? 'systemShare'
      : route.path.includes('resource-management')
        ? 'systemManage'
        : route.path.includes('share/')
          ? 'workspaceShare'
          : 'workspace',
  }),
)
const emit = defineEmits<{ close: [] }>()
const presentation = { show_avatar: false, show_user_avatar: false }
const visible = ref(false),
  streamBusy = ref(false),
  renderBusy = ref(false),
  recordBusy = ref(false)
const toolId = ref(''),
  initialInput = ref<Input>({}),
  retryInput = ref<Input>()
const chat = ref(newChat()),
  record = ref<ToolRecord>(),
  tab = ref('output')
const streamError = ref(''),
  recordError = ref('')
const steps = computed(() =>
  Object.values(record.value?.meta?.details || {}).sort(
    (left, right) => (left.index ?? Infinity) - (right.index ?? Infinity),
  ),
)
const statusText = computed(() => {
  if (streamBusy.value) return t('runTrace.states.running')
  if (recordBusy.value && !record.value) return t('views.tool.debugPanel.loadingRecord')
  if (!record.value) return ''
  if (
    record.value.state === 'SUCCESS' &&
    steps.value.some((n) => n.type === 'form-node' && n.is_submit === false)
  )
    return t('runTrace.states.waiting_input')
  const states: Record<string, string> = {
    SUCCESS: 'succeeded',
    FAILURE: 'failed',
    PENDING: 'queued',
    STARTED: 'running',
    REVOKED: 'cancelled',
  }
  const state = record.value.state
  return states[state] ? t('runTrace.states.' + states[state]) : state
})
let revision = 0
let reader: ReadableStreamDefaultReader<Uint8Array> | undefined
const answerControls = {
  // The drawer owns the writer during form continuation; inline chat controls may pause/resume it.
  stop: (id: string) => ChatManagement.stop(id),
  open: (id: string) => {
    if (streamBusy.value && ChatManagement.isStop(id)) ChatManagement.open(id)
  },
  write: (id: string) => {
    const writer = ChatManagement.chatMessageContainer[id]
    if (streamBusy.value && writer && !writer.is_close && !renderBusy.value)
      ChatManagement.write(id)
  },
}
function clearStream() {
  ++revision
  reader?.cancel().catch(() => {})
  reader = undefined
  ChatManagement.stop(chat.value.id)
  delete ChatManagement.chatMessageContainer[chat.value.id]
  streamBusy.value = false
  renderBusy.value = false
  recordBusy.value = false
}
function close() {
  visible.value = false
}
watch(
  visible,
  (show) => {
    if (!show) {
      clearStream()
      emit('close')
    }
  },
  { flush: 'sync' },
)
onBeforeUnmount(clearStream)

async function readRecord() {
  if (recordBusy.value || !chat.value.record_id) return
  const session = revision
  recordBusy.value = true
  recordError.value = ''
  try {
    const result = await api.value.getToolRecordDetail(toolId.value, chat.value.record_id)
    if (!result.data?.state) throw new Error(t('views.tool.debugPanel.recordError'))
    if (session === revision) record.value = result.data
  } catch (e) {
    if (session === revision)
      recordError.value = errorMessage(e, t('views.tool.debugPanel.recordError'))
  } finally {
    if (session === revision) recordBusy.value = false
  }
}
function applyFrame(frame: WorkflowFrame) {
  if (frame.chat_id) chat.value.chat_id = frame.chat_id
  if (frame.chat_record_id || frame.id) chat.value.record_id = (frame.chat_record_id || frame.id)!
  if (!frame.is_end && typeof frame.content === 'string')
    ChatManagement.appendChunk(
      chat.value.id,
      frame as Parameters<typeof ChatManagement.appendChunk>[1],
    )
  else if (frame.content) ChatManagement.append(chat.value.id, frame.content)
}
async function execute(inputs: Input, continuation = false): Promise<boolean> {
  if (streamBusy.value || !visible.value) return false
  const session = ++revision
  streamBusy.value = true
  recordBusy.value = false
  streamError.value = ''
  recordError.value = ''
  retryInput.value = undefined
  record.value = undefined
  const row = chat.value
  ChatManagement.stop(row.id)
  ChatManagement.addChatRecord(row, 25, renderBusy)
  ChatManagement.write(row.id)
  try {
    const response: Response = await api.value.debugToolWorkflow(toolId.value, inputs)
    if (session !== revision) {
      await response.body?.cancel()
      return false
    }
    if (!response.ok || response.headers.get('content-type')?.includes('json')) {
      const body = await response.json().catch(() => null)
      if (session !== revision) return false
      if (!response.ok || (body?.code !== undefined && body.code !== 200) || !body)
        throw new Error(
          body?.message ||
            body?.detail ||
            (response.ok ? t('views.tool.debugPanel.interrupted') : 'HTTP ' + response.status),
        )
      applyFrame({ ...body.data, is_end: true })
    } else {
      const stream = response.body?.getReader()
      if (!stream) throw new Error(t('views.tool.debugPanel.interrupted'))
      reader = stream
      try {
        const ended = await readWorkflowEvents(stream, (frame) => {
          if (session === revision) applyFrame(frame)
        })
        if (!ended) throw new Error(t('views.tool.debugPanel.interrupted'))
      } finally {
        if (reader === stream) reader = undefined
        stream.releaseLock()
      }
    }
    if (!row.record_id) throw new Error(t('views.tool.debugPanel.recordError'))
    return true
  } catch (e) {
    if (session === revision) {
      streamError.value = errorMessage(e, t('views.tool.debugPanel.interrupted'))
      // A form cannot submit itself twice; keep its payload for an explicit retry.
      if (continuation) retryInput.value = inputs
    }
    return false
  } finally {
    if (session === revision) {
      streamBusy.value = false
      ChatManagement.close(row.id)
      if (row.record_id) await readRecord()
    }
  }
}
function sendMessage(_question: string, params?: Input) {
  return execute({ ...initialInput.value, ...params }, true)
}
function retryContinuation() {
  if (retryInput.value) execute(retryInput.value, true)
}
function open(id: string, data: Input) {
  clearStream()
  toolId.value = id
  initialInput.value = data
  chat.value = newChat()
  tab.value = 'output'
  visible.value = true
  void execute(data)
}
defineExpose({ open, close })
</script>
<style scoped src="../../tool/component/tool-panel.css"></style>
<style scoped>
.refresh {
  justify-self: start;
}
.tool-result {
  margin-top: 12px;
}
.tool-drawer-body :deep(.el-tabs__content) {
  overflow-wrap: anywhere;
}
</style>
