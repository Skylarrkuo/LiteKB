<template>
  <div class="application-workflow" v-loading="loading">
    <div class="editor-header">
      <div class="editor-identity">
        <back-button :aria-label="$t('views.application.title')" @click="back" />
        <h4 class="editor-title ellipsis" :title="detail?.name">{{ detail?.name }}</h4>
        <div v-if="showHistory && disablePublic">
          <el-text type="info" class="ml-16 color-secondary"
            >{{ $t('workflow.info.previewVersion') }}
            {{ currentVersion.name || datetimeFormat(currentVersion.update_time) }}</el-text
          >
        </div>
        <el-text type="info" class="ml-16 color-secondary" v-else-if="saveTime"
          >{{ $t('workflow.info.saveTime') }}{{ datetimeFormat(saveTime) }}</el-text
        >
      </div>
      <div class="editor-actions" v-if="showHistory && disablePublic">
        <el-button type="primary" class="mr-8" @click="refreshVersion()">
          {{ $t('workflow.setting.restoreVersion') }}
        </el-button>
        <el-divider direction="vertical" />
        <el-button text :aria-label="$t('common.close')" @click="closeHistory">
          <el-icon>
            <Close />
          </el-icon>
        </el-button>
      </div>
      <div v-else class="editor-actions">
        <el-button class="add-node-trigger" :aria-expanded="showPopover" @click="showPopover = !showPopover">
          <AppIcon iconName="app-add-outlined" class="mr-4" />
          {{ $t('workflow.setting.addComponent') }}
        </el-button>
        <el-button
          class="model-settings-trigger"
          :aria-label="$t('workflow.setting.defaultModelSetting')"
          :title="$t('workflow.setting.defaultModelSetting')"
          :aria-expanded="defaultModelSettingVisible"
          @click="toggleDefaultModelSetting"
          v-if="permissionPrecise.debug(id)"
        >
          <AppIcon iconName="app-setting" class="mr-4"></AppIcon>
          <span class="model-settings-label">{{ $t('workflow.setting.defaultModelSetting') }}</span>
        </el-button>
        <el-button ref="debugTrigger" @click="clickShowDebug" :disabled="showDebug" v-if="permissionPrecise.debug(id)">
          <AppIcon iconName="app-debug-outlined" class="mr-4"></AppIcon>
          {{ $t('common.debug') }}
        </el-button>
        <el-button @click="saveApplication(true)" v-if="permissionPrecise.edit(id)">
          <AppIcon iconName="app-save-outlined" class="mr-4"></AppIcon>
          {{ $t('common.save') }}
        </el-button>
        <el-button type="primary" @click="publish" v-if="permissionPrecise.publish(id)">
          {{ $t('common.publish') }}
        </el-button>

        <el-dropdown trigger="click">
          <el-button text @click.stop :aria-label="$t('common.moreSettings')">
            <AppIcon iconName="app-more" class="rotate-90"></AppIcon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="openHistory">
                <AppIcon iconName="app-history-outlined" class="color-secondary"></AppIcon>
                {{ $t('workflow.setting.releaseHistory') }}
              </el-dropdown-item>
              <el-dropdown-item>
                <AppIcon iconName="app-save-outlined" class="color-secondary"></AppIcon>
                {{ $t('workflow.setting.autoSave') }}
                <div class="ml-4">
                  <el-switch size="small" v-model="isSave" @change="changeSave" />
                </div>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>
    <div class="workflow-main" ref="workflowMainRef">
      <workflow ref="workflowRef" v-if="detail" :data="detail?.work_flow" />
      <!-- 下拉框 -->
      <el-collapse-transition>
        <DropdownMenu
          :show="showPopover"
          :id="id"
          v-click-outside="clickoutside"
          @clickNodes="clickNodes"
          @onmousedown="onmousedown"
          :workflowRef="workflowRef"
        />
      </el-collapse-transition>
      <!-- 发布历史 -->
      <PublishHistory
        v-if="showHistory"
        @click="checkVersion"
        v-click-outside="clickoutsideHistory"
        @refreshVersion="refreshVersion"
      />

      <DefaultModelSettingMenu
        v-if="detail"
        ref="defaultsMenu"
        v-model="detail.default_model_setting"
        :show="defaultModelSettingVisible"
        :workflow-ref="workflowRef"
        :readonly="!permissionPrecise.edit(id)"
        @save="saveApplication(true)"
        @close="clickoutsideDefaultModelSetting"
      />
    </div>
    <section
      v-if="showDebug"
      class="workflow-debug-panel"
      :class="{ enlarge }"
      :aria-label="$t('common.debug')"
      @keydown.esc.stop="closeDebug"
    >
      <header class="debug-heading" :class="!isDefaultTheme ? 'custom-header' : ''">
        <el-avatar v-if="isAppIcon(detail?.icon)" shape="square" :size="32" class="debug-avatar">
          <img :src="resetUrl(detail.icon)" alt="" />
        </el-avatar>
        <LogoIcon v-else height="32px" />
        <div class="debug-title">
          <small>{{ $t('common.debug') }}</small>
          <h4 class="ellipsis" :title="detail?.name">{{ detail?.name || $t('common.name') }}</h4>
        </div>
        <el-button
          class="debug-resize" text :aria-pressed="enlarge"
          :aria-label="enlarge ? $t('common.collapse') : $t('common.expand')"
          :title="enlarge ? $t('common.collapse') : $t('common.expand')"
          @click="enlarge = !enlarge"
        >
          <AppIcon :iconName="enlarge ? 'app-minify' : 'app-magnify'" />
        </el-button>
        <button ref="debugClose" class="debug-close" type="button" :aria-label="$t('common.close')" @click="closeDebug">
          <el-icon><Close /></el-icon>
        </button>
      </header>
      <div class="debug-conversation">
        <AiChat :application-details="detail" type="debug-ai-chat" />
      </div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, nextTick, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { Action } from 'element-plus'
import Workflow from '@/workflow/index.vue'
import DropdownMenu from '@/components/workflow-dropdown-menu/index.vue'
import DefaultModelSettingMenu from '@/components/workflow-dropdown-menu/default-model-setting/index.vue'
import PublishHistory from '@/views/application-workflow/component/PublishHistory.vue'
import { isAppIcon, resetUrl } from '@/utils/common'
import { MsgSuccess, MsgError, MsgConfirm } from '@/utils/message'
import { datetimeFormat } from '@/utils/time'
import useStore from '@/stores'
import { WorkFlowInstance, validateWorkflowDefaultModels } from '@/workflow/common/validate'
import { hasPermission } from '@/utils/permission'
import { t } from '@/locales'
import { ComplexPermission } from '@/utils/permission/type'
import { EditionConst, PermissionConst, RoleConst } from '@/utils/permission/data'
import permissionMap from '@/permission'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import { WorkflowMode } from '@/enums/application'
provide('getResourceDetail', () => detail)
provide('workflowMode', WorkflowMode.Application)
provide('loopWorkflowMode', WorkflowMode.ApplicationLoop)
const { theme } = useStore()
const router = useRouter()
const route = useRoute()
const {
  params: { id, from },
} = route as any
const apiType = computed(() => {
  if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})

const permissionPrecise = computed(() => {
  return permissionMap['application'][apiType.value]
})

const isDefaultTheme = computed(() => {
  return theme.isDefaultTheme()
})

let interval: any
const workflowRef = ref()
const workflowMainRef = ref()
const loading = ref(false)
const detail = ref<any>(null)

const showPopover = ref(false)
const showDebug = ref(false)
const enlarge = ref(false)
const debugClose = ref<HTMLButtonElement>()
const debugTrigger = ref<{ $el: HTMLElement }>()

function closeDebug() {
  showDebug.value = false
  enlarge.value = false
  nextTick(() => debugTrigger.value?.$el.focus())
}
const saveTime = ref<any>('')
const isSave = ref(false)
const showHistory = ref(false)
const disablePublic = ref(false)
const currentVersion = ref<any>({})
const cloneWorkFlow = ref(null)

// ===== 默认模型设置 =====
const defaultModelSettingVisible = ref(false)
const defaultsMenu = ref<InstanceType<typeof DefaultModelSettingMenu>>()

function toggleDefaultModelSetting() {
  if (defaultModelSettingVisible.value) defaultsMenu.value?.requestClose()
  else defaultModelSettingVisible.value = true
}

function clickoutsideDefaultModelSetting() {
  defaultModelSettingVisible.value = false
}
// ===== 默认模型设置 End =====

function back() {
  if (JSON.stringify(cloneWorkFlow.value) !== JSON.stringify(getGraphData())) {
    MsgConfirm(t('common.tip'), t('workflow.tip.saveMessage'), {
      confirmButtonText: t('workflow.setting.exitSave'),
      cancelButtonText: t('workflow.setting.exit'),
      distinguishCancelAndClose: true,
    })
      .then(() => {
        saveApplication(true, true)
      })
      .catch((action: Action) => {
        if (action === 'cancel') {
          go()
        }
      })
  } else {
    go()
  }
}
function clickoutsideHistory() {
  if (!disablePublic.value) {
    showHistory.value = false
    disablePublic.value = false
  }
}

function refreshVersion(item?: any) {
  if (item) {
    renderGraphData(item)
  }
  // if (hasPermission(`APPLICATION:MANAGE:${id}`, 'AND') && isSave.value) {
  //   initInterval()
  // }
  showHistory.value = false
  disablePublic.value = false
}

function checkVersion(item: any) {
  disablePublic.value = true
  currentVersion.value = item
  renderGraphData(item)
  closeInterval()
}

function renderGraphData(item: any) {
  item.work_flow['nodes'].map((v: any) => {
    v['properties']['noRender'] = true
  })
  detail.value.work_flow = item.work_flow
  saveTime.value = item?.update_time
  workflowRef.value?.clearGraphData()
  nextTick(() => {
    workflowRef.value?.render(item.work_flow)
  })
}

function closeHistory() {
  getDetail()
  if (isSave.value) {
    initInterval()
  }
  showHistory.value = false
  disablePublic.value = false
}

function openHistory() {
  showHistory.value = true
}

function changeSave(bool: boolean) {
  if (bool) {
    initInterval()
  } else {
    closeInterval()
  }
  localStorage.setItem('workflowAutoSave', bool.toString())
}

function clickNodes(item: any) {
  showPopover.value = false
}

function onmousedown(item: any) {
  showPopover.value = false
}

function clickoutside(event: MouseEvent) {
  if ((event.target as Element)?.closest('.add-node-trigger')) return
  showPopover.value = false
}
const publish = () => {
  if (workflowRef.value?.isReadOnly()) return MsgError(t('studio.unavailableNodes'))
  workflowRef.value
    ?.validate()
    .then(() => {
      const workflow = getGraphData()
      const workflowInstance = new WorkFlowInstance(workflow)
      try {
        workflowInstance.is_valid()
      } catch (e: any) {
        MsgError(e.toString())
        return
      }
      // 发布前拦截「节点选默认模型但该类别默认模型未配置」,与后端 publish 校验一致,提前于保存请求
      validateWorkflowDefaultModels(workflow, detail.value?.default_model_setting || {})
      loadSharedApi({ type: 'application', systemType: apiType.value })
        .putApplication(
          id,
          { work_flow: workflow, default_model_setting: detail.value?.default_model_setting || {} },
          loading,
        )
        .then(() => {
          return loadSharedApi({ type: 'application', systemType: apiType.value }).publish(
            id,
            {},
            loading,
          )
        })
        .then((ok: any) => {
          detail.value.name = ok.data.name
          MsgSuccess(t('views.application.tip.publishSuccess'))
        })
        .catch((res: any) => {
          const node = res.node
          const err_message = res.errMessage
          workflowRef.value?.highlightNode(node)
          if (typeof err_message == 'string') {
            MsgError(
              res.node.properties?.stepName +
                ` ${t('workflow.node').toLowerCase()} ` +
                err_message.toLowerCase(),
            )
          } else {
            const keys = Object.keys(err_message)
            MsgError(
              node.properties?.stepName +
                ` ${t('workflow.node').toLowerCase()} ` +
                err_message[keys[0]]?.[0]?.message.toLowerCase(),
            )
          }
        })
    })
    .catch((res: any) => {
      const node = res.node
      const err_message = res.errMessage
      workflowRef.value?.highlightNode(node)
      if (typeof err_message == 'string') {
        MsgError(res.node.properties?.stepName + ` ${t('workflow.node')}，` + err_message)
      } else {
        const keys = Object.keys(err_message)
        MsgError(
          node.properties?.stepName +
            ` ${t('workflow.node')}，` +
            err_message[keys[0]]?.[0]?.message,
        )
      }
    })
}

const clickShowDebug = () => {
  if (workflowRef.value?.isReadOnly()) return MsgError(t('studio.unavailableNodes'))
  workflowRef.value
    ?.validate()
    .then(() => {
      const graphData = getGraphData()
      const workflow = new WorkFlowInstance(graphData)
      try {
        workflow.is_valid()
        detail.value = {
          ...detail.value,
          type: 'WORK_FLOW',
          ...workflow.get_base_node()?.properties.node_data,
          work_flow: getGraphData(),
        }

        showDebug.value = true
        nextTick(() => debugClose.value?.focus())
      } catch (e: any) {
        MsgError(e.toString())
      }
    })
    .catch((res: any) => {
      const node = res.node
      const err_message = res.errMessage
      if (typeof err_message == 'string') {
        MsgError(res.node.properties?.stepName + ` ${t('workflow.node')}，` + err_message)
      } else {
        const keys = Object.keys(err_message)
        MsgError(
          node.properties?.stepName +
            ` ${t('workflow.node')}，` +
            err_message[keys[0]]?.[0]?.message,
        )
      }
    })
}
function getGraphData() {
  return workflowRef.value?.getGraphData()
}

function getDetail() {
  loadSharedApi({ type: 'application', systemType: apiType.value })
    .getApplicationDetail(id)
    .then((res: any) => {
      res.data?.work_flow['nodes'].map((v: any) => {
        v['properties']['noRender'] = true
      })
      detail.value = res.data
      detail.value.stt_model_id = res.data.stt_model
      detail.value.tts_model_id = res.data.tts_model
      detail.value.tts_type = res.data.tts_type
      saveTime.value = res.data?.update_time
      workflowRef.value?.clearGraphData()
      nextTick(() => {
        workflowRef.value?.render(detail.value.work_flow)
        cloneWorkFlow.value = getGraphData()
      })
      // 企业版和专业版
      if (hasPermission([EditionConst.IS_EE, EditionConst.IS_PE], 'OR')) {
        loadSharedApi({ type: 'application', systemType: apiType.value })
          .getApplicationSetting(id)
          .then((ok: any) => {
            detail.value = { ...detail.value, ...ok.data }
          })
      }
    })
}

function saveApplication(bool?: boolean, back?: boolean) {
  if (workflowRef.value?.isReadOnly()) return
  const obj = {
    work_flow: getGraphData(),
    default_model_setting: detail.value?.default_model_setting || {},
  }
  loading.value = back || false
  loadSharedApi({ type: 'application', systemType: apiType.value })
    .putApplication(id, obj)
    .then(() => {
      saveTime.value = new Date()
      if (bool) {
        cloneWorkFlow.value = getGraphData()
        MsgSuccess(t('common.saveSuccess'))
        if (back) {
          go()
        }
      }
    })
    .catch(() => {
      loading.value = false
    })
}
const go = () => router.push({ path: get_route() })

const get_route = () => {
  if (
    hasPermission(
      [
        new ComplexPermission(
          [RoleConst.USER],
          [PermissionConst.APPLICATION.getApplicationWorkspaceResourcePermission(id)],
          [],
          'AND',
        ),
        RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
        PermissionConst.APPLICATION_OVERVIEW_READ.getWorkspacePermissionWorkspaceManageRole,
        PermissionConst.APPLICATION_OVERVIEW_READ.getApplicationWorkspaceResourcePermission(id),
      ],
      'OR',
    )
  ) {
    return `/application/${from}/${id}/WORK_FLOW/overview`
  } else if (
    hasPermission(
      [
        new ComplexPermission(
          [RoleConst.USER],
          [PermissionConst.APPLICATION.getApplicationWorkspaceResourcePermission(id)],
          [],
          'AND',
        ),
        PermissionConst.APPLICATION_CHAT_LOG_READ.getWorkspacePermissionWorkspaceManageRole,
        PermissionConst.APPLICATION_CHAT_LOG_READ.getApplicationWorkspaceResourcePermission(id),
      ],
      'OR',
    )
  ) {
    return `/application/${from}/${id}/WORK_FLOW/chat-log`
  } else return `/application`
}

/**
 * 定时保存
 */
const initInterval = () => {
  interval = setInterval(() => {
    saveApplication()
  }, 60000)
}

/**
 * 关闭定时
 */
const closeInterval = () => {
  if (interval) {
    clearInterval(interval)
  }
}


onMounted(() => {
  getDetail()
  const workflowAutoSave = localStorage.getItem('workflowAutoSave')
  isSave.value = workflowAutoSave === 'true' ? true : false
  // 初始化定时任务
  if (isSave.value) {
    initInterval()
  }
})

onBeforeUnmount(() => {
  // 清除定时任务
  closeInterval()
  workflowRef.value?.clearGraphData()
})
</script>
<style lang="scss" scoped>
.application-workflow {
  height: 100%;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--app-layout-bg-color);
}
.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  flex: none;
  gap: 8px 16px;
  padding: 12px clamp(12px, 2vw, 28px);
  border-bottom: 1px solid var(--studio-hairline);
  background: var(--app-header-bg-color);
}
.editor-identity, .editor-actions {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}
.editor-identity { flex: 1 1 160px; }
.editor-identity :deep(.el-text) { font-size: 12px; margin-left: 0; }
.editor-title { max-width: 26rem; font-size: 17px; }
.editor-actions {
  flex-wrap: wrap;
  :deep(.el-button) { margin-left: 0; border-radius: 10px; }
}
.workflow-main {
  flex: 1;
  position: relative;
  min-height: 0;
  overflow: hidden;
  > :deep(.workflow-dropdown-menu), > :deep(.workflow-publish-history) {
    inset-block: 12px auto;
    inset-inline: auto 12px;
    max-width: calc(100% - 24px);
    max-height: calc(100% - 24px);
    overflow: auto;
    box-sizing: border-box;
    border: 1px solid var(--studio-hairline);
    border-radius: var(--app-border-radius-large);
    box-shadow: var(--studio-shadow);
  }
  > :deep(.workflow-dropdown-menu .el-tabs__nav-wrap) { padding-inline: 12px; }
  :deep(.workflow-search), :deep(.workflow-search-button) { top: 16px; }
}
.workflow-debug-panel {
  position: fixed;
  z-index: 2000;
  right: 14px;
  bottom: 14px;
  display: flex;
  flex-direction: column;
  width: min(460px, calc(100vw - 28px));
  height: min(680px, calc(100dvh - 86px));
  border: 1px solid var(--studio-hairline);
  border-radius: 18px;
  box-sizing: border-box;
  background: var(--app-view-bg-color);
  box-shadow: 0 10px 36px rgb(22 75 80 / 14%);
  overflow: hidden;
  &.enlarge { width: min(760px, calc(100vw - 28px)); height: calc(100dvh - 28px); }
}
.debug-heading {
  flex: none;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--studio-hairline);
  background: var(--app-header-bg-color);
  .debug-avatar { background: transparent; }
}
.debug-title {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  flex: 1;
  min-width: 0;
  gap: 2px;
  small {
    font-size: 11px;
    line-height: 14px;
    color: var(--app-text-color-secondary);
  }
  h4 {
    display: block;
    max-width: none;
    margin: 0;
    font-size: 16px;
    line-height: 21px;
    font-weight: 650;
  }
}
.debug-close, .debug-resize {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--studio-ink);
  font-size: 17px;
  cursor: pointer;
  &:hover { background: var(--studio-selection); }
}
.debug-conversation {
  flex: 1;
  min-height: 0;
  :deep(.ai-chat.debug-ai-chat) { height: 100% !important; }
  :deep(.ai-chat > .el-scrollbar) { flex: 1; min-height: 0; }
  :deep(.debug-ai-chat .ai-chat__content) { padding-top: 16px; }
  :deep(.chat-width) { max-width: 100% !important; }
  :deep(.debug-ai-chat .question-content > .content) {
    background: var(--studio-selection);
    color: var(--studio-ink);
    border-radius: var(--app-border-radius-large);
  }
  :deep(.debug-ai-chat .operate-textarea) {
    border-color: var(--studio-hairline);
    border-radius: var(--app-border-radius-large);
    box-shadow: none;
  }
  :deep(.debug-ai-chat .question-content__operate .operate-textarea) {
    background: var(--studio-selection);
    color: var(--studio-ink);
  }
  :deep(.debug-ai-chat .operate-textarea:has(.el-textarea__inner:focus)) {
    border-color: var(--studio-ink);
    box-shadow: inset 0 0 0 1px var(--studio-ink);
  }
  :deep(.debug-ai-chat .operate-textarea .el-textarea__inner) {
    background-color: transparent;
    border-radius: var(--app-border-radius-large) !important;
    box-shadow: none;
    &:focus-visible { outline: none !important; }
  }
}
@media (max-width: 840px) {
  .editor-identity { flex-basis: 100%; }
  .editor-actions { gap: 5px; }
}
@media (max-width: 570px) {
  .editor-header { padding: 8px; }
  .editor-actions {
    :deep(.el-button) { padding-inline: 8px; }
    .model-settings-label { display: none; }
    .model-settings-trigger :deep(.app-icon) { margin-right: 0 !important; }
  }
  .workflow-debug-panel, .workflow-debug-panel.enlarge {
    inset: 0;
    width: 100%;
    height: 100dvh;
    border: 0;
    border-radius: 0;
    padding-bottom: env(safe-area-inset-bottom);
  }
  .debug-resize { display: none; }
}
</style>
