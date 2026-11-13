<template>
  <ContentContainer class="tool-library">
    <template #header>
      <slot name="header"></slot>
    </template>
    <template #search>
      <div class="tool-toolbar">
        <div class="flex-between complex-search">
          <el-select
            class="complex-search__left"
            :aria-label="$t('views.tool.library.scope')"
            v-model="search_type"
            style="width: 90px"
            @change="search_type_change"
          >
            <el-option :label="$t('common.creator')" value="create_user" />
            <el-option :label="$t('common.name')" value="name" />
          </el-select>
          <el-input
            v-if="search_type === 'name'"
            v-model="search_form.name"
            :aria-label="$t('common.name')"
            @change="searchHandle"
            :placeholder="$t('common.searchBar.placeholder')"
            style="width: 190px"
            clearable
          />
          <el-select
            v-else-if="search_type === 'create_user'"
            v-model="search_form.create_user"
            :aria-label="$t('common.creator')"
            @change="searchHandle"
            filterable
            clearable
            remote
            :remote-method="getUserList"
            style="width: 190px"
          >
            <el-option v-for="u in user_options" :key="u.id" :value="u.id" :label="u.nick_name" />
          </el-select>
        </div>
        <span
          class="ml-8"
          v-if="!isShared && (permissionPrecise.batchMove() || permissionPrecise.batchDelete())"
        >
          <el-button @click="batchSelectedHandle(true)" v-if="isBatch === false">
            <AppIcon iconName="app-batch-delete" class="mr-4" />
            {{ $t('views.paragraph.setting.batchSelected') }}
          </el-button>
          <el-button @click="batchSelectedHandle(false)" v-if="isBatch === true">
            <AppIcon iconName="app-batch-delete" class="mr-4" />
            {{ $t('views.paragraph.setting.cancelSelected') }}
          </el-button>
        </span>
        <div v-if="!isBatch && !isShared" class="tool-actions">
          <span class="ml-8" v-if="!isShared && permissionPrecise.create()">
            <el-button
              class="browse-tools"
              data-testid="tool-store-open"
              @click="openToolStoreDialog()"
            >
              <AppIcon iconName="app-tool-store" class="mr-4" />
              {{ $t('views.tool.toolStore.title') }}
            </el-button>
          </span>

          <el-button
            v-if="permissionPrecise.import()"
            data-testid="tool-import-open"
            :icon="Upload"
            @click="openImport"
          >
            {{ $t('views.tool.library.importFile') }}
          </el-button>
          <el-dropdown trigger="click" v-if="permissionPrecise.create() || canCreateFolder">
            <el-button type="primary" data-testid="tool-create-open">
              {{ $t('common.create') }}
              <el-icon class="el-icon--right">
                <arrow-down />
              </el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu class="create-dropdown">
                <template v-if="permissionPrecise.create()">
                  <el-dropdown-item @click="openCreateDialog()">
                    <div class="flex align-center">
                      <el-avatar class="avatar-green" shape="square" :size="32">
                        <img src="@/assets/tool/icon_tool.svg" style="width: 58%" alt="" />
                      </el-avatar>
                      <div class="pre-wrap ml-8">
                        <div class="lighter">{{ $t('views.tool.title') }}</div>
                      </div>
                    </div>
                  </el-dropdown-item>
                  <el-dropdown-item @click="openCreateWorkflowDialog()">
                    <div class="flex align-center">
                      <el-avatar class="avatar-green mt-4" shape="square" :size="32">
                        <img src="@/assets/workflow/logo_workflow.svg" style="width: 60%" alt="" />
                      </el-avatar>
                      <div class="pre-wrap ml-8">
                        <div class="lighter">{{ $t('workflow.workflow') }}</div>
                      </div>
                    </div>
                  </el-dropdown-item>
                  <el-dropdown-item @click="openCreateSkillDialog()">
                    <div class="flex align-center">
                      <el-avatar shape="square" :size="32">
                        <img src="@/assets/tool/icon_skill.svg" style="width: 58%" alt="" />
                      </el-avatar>
                      <div class="pre-wrap ml-8">
                        <div class="lighter">Skills</div>
                      </div>
                    </div>
                  </el-dropdown-item>
                  <el-dropdown-item @click="openCreateMcpDialog()">
                    <div class="flex align-center">
                      <el-avatar shape="square" :size="32">
                        <img src="@/assets/tool/icon_mcp.svg" style="width: 75%" alt="" />
                      </el-avatar>
                      <div class="pre-wrap ml-8">
                        <div class="lighter">MCP</div>
                      </div>
                    </div>
                  </el-dropdown-item>

                  <el-dropdown-item @click="openCreateDataSourceDialog()">
                    <div class="flex align-center">
                      <el-avatar class="avatar-purple" shape="square" :size="32">
                        <img src="@/assets/tool/icon_datasource.svg" style="width: 58%" alt="" />
                      </el-avatar>
                      <div class="pre-wrap ml-8">
                        <div class="lighter">{{ $t('views.tool.dataSource.title') }}</div>
                      </div>
                    </div>
                  </el-dropdown-item>
                </template>
                <el-dropdown-item
                  @click="openCreateFolder"
                  :divided="permissionPrecise.create()"
                  v-if="canCreateFolder"
                >
                  <div class="flex align-center">
                    <AppIcon iconName="app-folder" style="font-size: 32px"></AppIcon>

                    <div class="pre-wrap ml-4">
                      <div class="lighter">
                        {{ $t('components.folder.addFolder') }}
                      </div>
                    </div>
                  </div>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </template>

    <div v-loading="paginationConfig.current_page === 1 && listBusy" class="tool-results">
      <div v-if="listError" class="tool-notice" role="alert">
        {{ $t('views.tool.library.listError') }}
        <el-button link type="primary" @click="getList">{{
          $t('views.tool.library.retry')
        }}</el-button>
      </div>
      <InfiniteScroll
        :size="tool.toolList.length"
        :total="paginationConfig.total"
        :page_size="paginationConfig.page_size"
        v-model:current_page="paginationConfig.current_page"
        @load="getList"
        :loading="listBusy || listError"
      >
        <el-checkbox-group v-model="multipleSelection" @change="handleCheckedChatChange">
          <el-row v-if="tool.toolList.length > 0" :gutter="15" class="w-full">
            <template v-for="item in tool.toolList" :key="item.id">
              <el-col :xs="24" :sm="12" :md="12" :lg="8" :xl="6" class="mb-16">
                <CardBox
                  :title="item.name"
                  :description="item.desc"
                  class="cursor"
                  :class="{
                    'border-active': multipleSelection.includes(item.id),
                  }"
                  @click.stop="openCard(item)"
                >
                  <template #icon>
                    <el-avatar v-if="item?.icon" shape="square" :size="32" style="background: none">
                      <img :src="resetUrl(item?.icon)" alt="" />
                    </el-avatar>
                    <ToolIcon v-else :size="32" :type="item?.tool_type" />
                  </template>
                  <template #title>
                    <div class="flex align-center">
                      <span class="ellipsis-1" :title="item.name">
                        {{ item.name }}
                      </span>
                      <el-tag
                        v-if="item.version"
                        class="ml-4"
                        size="small"
                        type="info"
                        effect="plain"
                      >
                        {{ item.version }}
                      </el-tag>
                    </div>
                  </template>
                  <template #subTitle>
                    <el-text class="color-secondary lighter flex align-center" size="small">
                      <span
                        :title="i18n_name(item.nick_name)"
                        class="ellipsis"
                        style="max-width: 90px"
                      >
                        {{ i18n_name(item.nick_name) }}
                      </span>
                      <span class="ml-4 mr-4"> {{ $t('common.createdIn') }}</span>
                      <span> {{ dateFormat(item.create_time) }}</span>
                    </el-text>
                  </template>
                  <template #tag="{ hoverShow }">
                    <el-checkbox :value="item.id" :aria-label="item.name" v-if="isBatch" @click.stop />
                    <div v-else>
                      <el-tag v-if="isShared" size="small" type="info" class="info-tag">
                        {{ t('views.shared.title') }}
                      </el-tag>
                      <el-tooltip
                        effect="dark"
                        :content="$t('views.tool.updatedVersion')"
                        v-if="
                          showUpdateStoreTool(item) && !isShared && permissionPrecise.edit(item.id)
                        "
                      >
                        <el-button text @click.stop="updateStoreTool(item)">
                          <el-icon v-if="hoverShow">
                            <Refresh />
                          </el-icon>
                          <div v-else class="dot-success"></div>
                        </el-button>
                      </el-tooltip>
                    </div>
                  </template>

                  <template #footer>
                    <div v-if="item.is_active" class="flex align-center">
                      <el-icon class="color-success mr-8" style="font-size: 16px">
                        <SuccessFilled />
                      </el-icon>
                      <span class="color-secondary">
                        {{ $t('common.status.enabled') }}
                      </span>
                    </div>
                    <div v-else class="flex align-center">
                      <AppIcon iconName="app-disabled" class="color-secondary mr-8"></AppIcon>
                      <span class="color-secondary">
                        {{ $t('common.status.disabled') }}
                      </span>
                    </div>
                  </template>
                  <template #mouseEnter>
                    <div @click.stop v-if="!isBatch && !isShared && MoreFieldPermission(item.id)">
                      <el-switch
                        :model-value="item.is_active"
                        :disabled="changeStateloading"
                        @change="changeState(item)"
                        size="small"
                        :aria-label="item.name + ' · ' + $t('common.status.enabled')"
                        class="mr-4"
                        v-if="permissionPrecise.switch(item.id)"
                      />
                      <el-divider direction="vertical" />
                      <el-dropdown trigger="click">
                        <el-button text @click.stop>
                          <AppIcon iconName="app-more" class="color-secondary"></AppIcon>
                        </el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item
                              v-if="item.tool_type === 'MCP'"
                              @click.stop="showMcpConfig(item)"
                            >
                              <AppIcon iconName="app-operate-log" class="color-secondary"></AppIcon>
                              {{ $t('views.tool.mcp.mcpConfig') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              v-if="item.template_id && permissionPrecise.edit(item.id)"
                              @click.stop="addInternalTool(item, true)"
                            >
                              <AppIcon iconName="app-edit" class="color-secondary"></AppIcon>
                              {{ $t('common.edit') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              v-else-if="
                                item.tool_type === 'WORKFLOW' && permissionPrecise.edit(item.id)
                              "
                              @click.stop="openCreateWorkflowDialog(item)"
                            >
                              <AppIcon iconName="app-edit" class="color-secondary"></AppIcon>
                              {{ $t('common.edit') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              v-else-if="permissionPrecise.edit(item.id)"
                              @click.stop="openEditDialog(item)"
                            >
                              <AppIcon iconName="app-edit" class="color-secondary"></AppIcon>
                              {{ $t('common.edit') }}
                            </el-dropdown-item>

                            <el-dropdown-item
                              v-if="item.tool_type === 'WORKFLOW'"
                              @click.stop="toWorkflow(item)"
                            >
                              <AppIcon iconName="app-workflow" class="color-secondary"></AppIcon>
                              {{ $t('workflow.workflow') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              v-if="!item.template_id && permissionPrecise.copy(item.id)"
                              @click.stop="copyTool(item)"
                            >
                              <AppIcon iconName="app-copy" class="color-secondary"></AppIcon>
                              {{ $t('common.copy') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              v-if="
                                item.init_field_list?.length > 0 && permissionPrecise.edit(item.id)
                              "
                              @click.stop="configInitParams(item)"
                            >
                              <AppIcon iconName="app-operation" class="color-secondary"></AppIcon>
                              {{ $t('common.param.initParam') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              @click.stop="openAuthorization(item)"
                              v-if="apiType === 'workspace' && permissionPrecise.auth(item.id)"
                            >
                              <AppIcon
                                iconName="app-resource-authorization"
                                class="color-secondary"
                              ></AppIcon>
                              {{ $t('views.system.resourceAuthorization.title') }}
                            </el-dropdown-item>

                            <el-dropdown-item
                              text
                              @click.stop="openResourceMappingDrawer(item)"
                              v-if="permissionPrecise.relate_map(item.id)"
                            >
                              <AppIcon
                                iconName="app-resource-mapping"
                                class="color-secondary"
                              ></AppIcon>
                              {{ $t('views.system.resourceMapping.title') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              text
                              @click.stop="openToolRecordDrawer(item)"
                              v-if="
                                (item.tool_type === 'CUSTOM' || item.tool_type === 'WORKFLOW') &&
                                permissionPrecise.record(item.id)
                              "
                            >
                              <AppIcon
                                iconName="app-schedule-report"
                                class="color-secondary"
                              ></AppIcon>
                              {{ $t('common.ExecutionRecord.subTitle') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              @click.stop="openMoveToDialog(item)"
                              v-if="permissionPrecise.copy(item.id) && apiType === 'workspace'"
                            >
                              <AppIcon iconName="app-migrate" class="color-secondary"></AppIcon>
                              {{ $t('common.moveTo') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              v-if="isSystemShare && permissionPrecise.auth_to_workspace()"
                              @click.stop="openAuthorizedWorkspaceDialog(item)"
                            >
                              <AppIcon iconName="app-lock" class="color-secondary"></AppIcon>
                              {{ $t('views.shared.authorized_workspace') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              v-if="!item.template_id && permissionPrecise.export(item.id)"
                              @click.stop="exportTool(item)"
                            >
                              <AppIcon iconName="app-export" class="color-secondary"></AppIcon>
                              {{ $t('common.export') }}
                            </el-dropdown-item>
                            <el-dropdown-item
                              v-if="permissionPrecise.delete(item.id)"
                              divided
                              @click.stop="deleteTool(item)"
                            >
                              <AppIcon iconName="app-delete" class="color-secondary"></AppIcon>
                              {{ $t('common.delete') }}
                            </el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                    </div>
                  </template>
                </CardBox>
              </el-col>
            </template>
          </el-row>
          <el-empty
            v-else-if="!listBusy && !listError"
            :image-size="70"
            :description="
              search_form[search_type] || tool.tool_type
                ? $t('views.tool.library.noMatch')
                : $t('views.tool.library.empty')
            "
          />
        </el-checkbox-group>
      </InfiniteScroll>
    </div>
    <!-- 批量操作拦 -->
    <div class="mul-operation border-t w-full flex align-center" v-if="isBatch">
      <el-checkbox
        v-model="checkAll"
        :indeterminate="isIndeterminate"
        @change="handleCheckAllChange"
      >
        {{ $t('common.allCheck') }}
      </el-checkbox>
      <el-button
        class="ml-16"
        :disabled="multipleSelection.length === 0"
        @click="openMoveToDialog()"
        v-if="permissionPrecise.batchMove()"
      >
        {{ $t('common.moveTo') }}
      </el-button>

      <el-button
        :disabled="multipleSelection.length === 0"
        @click="deleteMulTool"
        v-if="permissionPrecise.batchDelete()"
      >
        {{ $t('common.delete') }}
      </el-button>
      <span class="color-secondary ml-24 mr-16">
        {{ $t('common.selected') }} {{ multipleSelection.length }}/{{ paginationConfig.total }}
        {{ $t('views.document.items') }}
      </span>
      <el-button link type="primary" @click="batchSelectedHandle(false)">
        {{ $t('views.paragraph.setting.cancelSelected') }}
      </el-button>
    </div>
    <InitParamDrawer ref="InitParamDrawerRef" @refresh="refresh" @saved="({ id }) => toolStoreDescDrawerRef?.reload(id)" />
    <ToolDebugDrawer ref="savedDebugRef" />
    <WorkflowDebugDrawer ref="workflowDebugRef" />
    <ToolFormDrawer ref="ToolFormDrawerRef" @refresh="refresh" @created="openSaved" :title="ToolDrawertitle" />
    <McpToolFormDrawer ref="McpToolFormDrawerRef" @refresh="refresh" @created="openSaved" :title="McpToolDrawertitle" />
    <SkillToolFormDrawer
      ref="SkillToolFormDrawerRef"
      @created="openSaved"
      @refresh="refresh"
      :title="SkillToolDrawertitle"
    />
    <DataSourceToolFormDrawer
      ref="DataSourceToolFormDrawerRef"
      @created="openSaved"
      @refresh="refresh"
      :title="DataSourceToolDrawertitle"
    />
    <CreateFolderDialog ref="CreateFolderDialogRef" v-if="!isShared" @refresh="refreshFolder" />
    <ToolStoreDialog ref="toolStoreDialogRef" :api-type="apiType" @refresh="afterImport" />
    <ToolImportDialog ref="importDialogRef" :api-type="apiType" @imported="afterImport" />
    <AddInternalToolDialog ref="AddInternalToolDialogRef" @refresh="confirmAddInternalTool" />
    <McpToolConfigDialog ref="McpToolConfigDialogRef" @refresh="refresh" />
    <AuthorizedWorkspace
      ref="AuthorizedWorkspaceDialogRef"
      v-if="isSystemShare"
    ></AuthorizedWorkspace>
    <MoveToDialog
      ref="MoveToDialogRef"
      :source="SourceTypeEnum.TOOL"
      @refresh="refreshToolList"
      v-if="apiType === 'workspace'"
    />
    <ResourceAuthorizationDrawer
      :type="SourceTypeEnum.TOOL"
      ref="ResourceAuthorizationDrawerRef"
      v-if="apiType === 'workspace'"
    />
    <ToolStoreDescDrawer ref="toolStoreDescDrawerRef" :fetch-tool="fetchDetail" :catalog="storeTools"
      :editable="canEditSaved" :debuggable="canDebugSaved" :switchable="id => !isShared && permissionPrecise.switch(id)"
      :switch-busy="changeStateloading"
      @edit="editFromDetail" @configure="row => InitParamDrawerRef.open(row)" @debug="debugSaved" @toggle="changeState" />
    <ResourceMappingDrawer ref="resourceMappingDrawerRef"></ResourceMappingDrawer>
    <ExecutionRecordDrawer ref="toolRecordDrawerRef" />
    <WorkflowFormDialog
      ref="workflowFormDialogRef"
      @refresh="refresh"
      :title="workflowFormDialogTitle"
    ></WorkflowFormDialog>
  </ContentContainer>
</template>

<script lang="ts" setup>
import { onBeforeUnmount, onMounted, ref, reactive, computed, watch } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import { hasStartupValue } from '../startup-values'
import ToolImportDialog from './ToolImportDialog.vue'
import { cloneDeep } from 'lodash'
import { useRoute, onBeforeRouteLeave, useRouter } from 'vue-router'
import type { CheckboxValueType } from 'element-plus'
import InitParamDrawer from '@/views/tool/component/InitParamDrawer.vue'
import ToolFormDrawer from '@/views/tool/ToolFormDrawer.vue'
import ToolDebugDrawer from '@/views/tool/ToolDebugDrawer.vue'
import WorkflowDebugDrawer from '@/views/tool-workflow/debug-drawer/DebugDrawer.vue'
import McpToolFormDrawer from '@/views/tool/McpToolFormDrawer.vue'
import SkillToolFormDrawer from '@/views/tool/SkillToolFormDrawer.vue'
import DataSourceToolFormDrawer from '@/views/tool/DataSourceToolFormDrawer.vue'
import CreateFolderDialog from '@/components/folder-virtualized-tree/CreateFolderDialog.vue'
import AuthorizedWorkspace from '@/views/system-shared/AuthorizedWorkspaceDialog.vue'
import ToolStoreDialog from '@/views/tool/tool-store/ToolStoreDialog.vue'
import AddInternalToolDialog from '@/views/tool/tool-store/AddInternalToolDialog.vue'
import MoveToDialog from '@/components/folder-virtualized-tree/MoveToDialog.vue'
import ResourceAuthorizationDrawer from '@/components/resource-authorization-drawer/index.vue'
import McpToolConfigDialog from '@/views/tool/component/McpToolConfigDialog.vue'
import ToolStoreDescDrawer from '@/views/tool/component/ToolStoreDescDrawer.vue'
import ResourceMappingDrawer from '@/components/resource_mapping/index.vue'
import WorkflowFormDialog from '../WorkflowFormDialog.vue'
import ExecutionRecordDrawer from '@/views/tool-workflow/execution-record/ExecutionRecordDrawer.vue'
import ToolStoreApi from '@/api/tool/store.ts'
import { resetUrl, i18n_name } from '@/utils/common'
import { MsgSuccess, MsgConfirm, MsgError } from '@/utils/message'
import { SourceTypeEnum } from '@/enums/common'
import { dateFormat } from '@/utils/time'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import permissionMap from '@/permission'
import useStore from '@/stores'
import { t } from '@/locales'

import bus from '@/bus'

const router = useRouter()
const route = useRoute()

const { folder, user, tool } = useStore()
onBeforeRouteLeave(() => {
  ++listRequest
  tool.setToolList([])
})
const emit = defineEmits(['refreshFolder'])

const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})

const isShared = computed(() => {
  return folder.currentFolder?.id === 'share'
})
const isSystemShare = computed(() => {
  return apiType.value === 'systemShare'
})

const permissionPrecise = computed(() => {
  return permissionMap['tool'][apiType.value]
})
const canCreateFolder = computed(
  () =>
    apiType.value === 'workspace' &&
    folder.currentFolder?.id &&
    permissionPrecise.value.folderCreate(folder.currentFolder.id),
)

const MoreFieldPermission = (id: any) => {
  return (
    permissionPrecise.value.edit(id) ||
    permissionPrecise.value.switch(id) ||
    permissionPrecise.value.copy(id) ||
    permissionPrecise.value.export(id) ||
    permissionPrecise.value.delete(id) ||
    permissionPrecise.value.auth(id) ||
    permissionPrecise.value.relate_map(id) ||
    permissionPrecise.value.record(id) ||
    isSystemShare.value
  )
}

const resourceMappingDrawerRef = ref<InstanceType<typeof ResourceMappingDrawer>>()
const openResourceMappingDrawer = (tool: any) => {
  resourceMappingDrawerRef.value?.open('TOOL', tool)
}

const ResourceAuthorizationDrawerRef = ref()

function openAuthorization(item: any) {
  ResourceAuthorizationDrawerRef.value.open(item.id)
}

const toolRecordDrawerRef = ref<InstanceType<typeof ExecutionRecordDrawer>>()
const openToolRecordDrawer = (data: any) => {
  toolRecordDrawerRef.value?.open(data)
}

const InitParamDrawerRef = ref()
const search_type = ref('name')
const search_form = ref<any>({
  name: '',
  create_user: '',
})
const user_options = ref<any[]>([])

const loading = ref(false)
const listBusy = ref(false)
const listError = ref(false)
let listRequest = 0
const changeStateloading = ref(false)
const paginationConfig = reactive({
  current_page: 1,
  page_size: 30,
  total: 0,
})

const search_type_change = () => {
  search_form.value = { name: '', create_user: '' }
  searchHandle()
}
const ToolFormDrawerRef = ref()
const McpToolFormDrawerRef = ref()
const SkillToolFormDrawerRef = ref()
const DataSourceToolFormDrawerRef = ref()
const ToolDrawertitle = ref('')
const McpToolDrawertitle = ref('')
const SkillToolDrawertitle = ref('')
const DataSourceToolDrawertitle = ref('')

// 批量操作
const isBatch = ref(false)
const multipleSelection = ref<any[]>([])
const checkAll = ref(false)
const isIndeterminate = computed(() => {
  return multipleSelection.value.length > 0 && multipleSelection.value.length < tool.toolList.length
})

function batchSelectedHandle(bool: boolean) {
  isBatch.value = bool
  multipleSelection.value = []
  checkAll.value = false
}

const handleCheckAllChange = (val: CheckboxValueType) => {
  let bool
  if (isIndeterminate.value) {
    bool = true
  } else {
    bool = val as boolean
  }
  multipleSelection.value = bool ? tool.toolList.map((v) => v.id) : []
  checkAll.value = bool as boolean
}
const handleCheckedChatChange = (value: CheckboxValueType[]) => {
  const checkedCount = value.length
  checkAll.value = checkedCount === tool.toolList.length
}

function deleteMulTool() {
  MsgConfirm(
    `${t('views.document.delete.confirmTitle1')} ${multipleSelection.value.length} ${t('views.tool.delete.confirmTitle2')}`,
    t('views.paragraph.delete.confirmMessage'),
    {
      confirmButtonText: t('common.confirm'),
      confirmButtonClass: 'danger',
    },
  )
    .then(() => {
      loadSharedApi({ type: 'tool', systemType: apiType.value })
        .delMulTool(multipleSelection.value, loading)
        .then(() => {
          batchSelectedHandle(false)
          paginationConfig.current_page = 1
          tool.setToolList([])
          getList()
          MsgSuccess(t('views.document.delete.successMessage'))
        })
    })
    .catch(() => {})
}

function openCard(data: any) {
  if (isBatch.value) {
    const index = multipleSelection.value.indexOf(data?.id)
    if (index === -1) {
      multipleSelection.value.push(data?.id)
    } else {
      multipleSelection.value.splice(index, 1)
    }
    checkAll.value = multipleSelection.value.length === tool.toolList.length
    return
  }
  openSaved(data)
}

function openEditDialog(data?: any) {
  if (!permissionPrecise.value.edit(data?.id)) {
    return
  }
  // 共享过来的工具不让编辑
  if (isShared.value) {
    return
  }
  if (data) {
    bus.emit('select_node', data.folder_id)
  }
  if (data?.template_id) return

  // mcp工具
  if (data?.tool_type === 'MCP') {
    openCreateMcpDialog(data)
    return
  }
  // 数据源工具
  if (data?.tool_type === 'DATA_SOURCE') {
    openCreateDataSourceDialog(data)
    return
  }
  // 技能
  if (data?.tool_type === 'SKILL') {
    openCreateSkillDialog(data)
    return
  }
  // 工作流
  if (data?.tool_type === 'WORKFLOW') {
    toWorkflow(data)
    return
  }
  ToolDrawertitle.value = t('views.tool.editTool')
  if (data) {
    loadSharedApi({ type: 'tool', systemType: apiType.value })
      .getToolById(data?.id, loading)
      .then((res: any) => {
        ToolFormDrawerRef.value.open(res.data)
      })
  }
}

const MoveToDialogRef = ref()

function openMoveToDialog(data?: any) {
  let obj
  if (isBatch.value) {
    obj = {
      id_list: multipleSelection.value,
    }
  } else {
    obj = {
      id: data.id,
      folder_id: data.folder,
    }
  }

  MoveToDialogRef.value?.open(obj)
}

function refreshToolList(row: any) {
  if (row) {
    // 不是根目录才会移除
    if (folder.currentFolder?.parent_id) {
      const list = cloneDeep(tool.toolList)
      const index = list.findIndex((v) => v.id === row.id)
      list.splice(index, 1)
      tool.setToolList(list)
    }
  } else {
    batchSelectedHandle(false)
    paginationConfig.current_page = 1
    tool.setToolList([])
    getList()
  }
}

const AuthorizedWorkspaceDialogRef = ref()

function openAuthorizedWorkspaceDialog(row: any) {
  if (AuthorizedWorkspaceDialogRef.value) {
    AuthorizedWorkspaceDialogRef.value.open(row, 'Tool')
  }
}

const toolStoreDescDrawerRef = ref<InstanceType<typeof ToolStoreDescDrawer>>()
const savedDebugRef = ref<InstanceType<typeof ToolDebugDrawer>>()
const workflowDebugRef = ref<InstanceType<typeof WorkflowDebugDrawer>>()
function openSaved(data: any) {
  if (data?.id) toolStoreDescDrawerRef.value?.open(data)
}
function fetchDetail(id: string) {
  if (isShared.value) {
    const row = tool.toolList.find(item => item.id === id)
    return row ? Promise.resolve({ data: row }) : Promise.reject(new Error('Tool not found'))
  }
  return loadSharedApi({ type: 'tool', systemType: apiType.value }).getToolById(id)
}
function canEditSaved(id: string) {
  return !isShared.value && permissionPrecise.value.edit(id)
}
function canDebugSaved(id: string) {
  return apiType.value === 'workspace' && canEditSaved(id)
}
function debugSaved(data: any) {
  if (!canDebugSaved(data.id) || !data.execution?.available) return
  if (data.execution.debug_mode === 'workflow') workflowDebugRef.value?.open(data.id, data)
  else savedDebugRef.value?.openSaved(data)
}
function editFromDetail(data: any) {
  if (!canEditSaved(data.id)) return
  if (data.template_id) addInternalTool(data, true)
  else if (data.tool_type === 'WORKFLOW') openCreateWorkflowDialog(data)
  else openEditDialog(data)
}

function openCreateDialog() {
  ToolDrawertitle.value = t('views.tool.createTool')
  ToolFormDrawerRef.value.open()
}

function openCreateMcpDialog(data?: any) {
  // 有template_id的不允许编辑，是模板转换来的
  if (data?.template_id) {
    return
  }
  // 共享过来的工具不让编辑
  if (isShared.value) {
    return
  }
  McpToolDrawertitle.value = data
    ? t('views.tool.mcp.editMcpTool')
    : t('views.tool.mcp.createMcpTool')
  if (data) {
    loadSharedApi({ type: 'tool', systemType: apiType.value })
      .getToolById(data?.id, loading)
      .then((res: any) => {
        McpToolFormDrawerRef.value.open(res.data)
      })
  } else {
    McpToolFormDrawerRef.value.open(data)
  }
}

function openCreateSkillDialog(data?: any) {
  // 有template_id的不允许编辑，是模板转换来的
  if (data?.template_id) {
    return
  }
  // 共享过来的工具不让编辑
  if (isShared.value) {
    return
  }
  SkillToolDrawertitle.value = data
    ? t('views.tool.skill.editSkillTool')
    : t('views.tool.skill.createSkillTool')
  if (data) {
    loadSharedApi({ type: 'tool', systemType: apiType.value })
      .getToolById(data?.id, loading)
      .then((res: any) => {
        SkillToolFormDrawerRef.value.open(res.data)
      })
  } else {
    SkillToolFormDrawerRef.value.open(data)
  }
}

function toWorkflow(data: any) {
  const folderId = data.scope === 'SHARED' ? 'shared' : data.folder_id
  router.push({ name: 'ToolWorkflow', params: { id: data.id, folderId: folderId } })
}

const workflowFormDialogRef = ref<InstanceType<typeof WorkflowFormDialog>>()
const workflowFormDialogTitle = ref('')
const openCreateWorkflowDialog = (data?: any) => {
  // 有template_id的不允许编辑，是模板转换来的
  if (data?.template_id) {
    return
  }
  // 共享过来的工具不让编辑
  if (isShared.value) {
    return
  }
  workflowFormDialogTitle.value = data
    ? t('common.edit')
    : t('views.tool.toolWorkflow.creatToolWorkflow')
  if (data) {
    loadSharedApi({ type: 'tool', systemType: apiType.value })
      .getToolById(data?.id, loading)
      .then((res: any) => {
        workflowFormDialogRef.value?.open(res.data)
      })
  } else {
    workflowFormDialogRef.value?.open(data)
  }
}

function openCreateDataSourceDialog(data?: any) {
  // 有template_id的不允许编辑，是模板转换来的
  if (data?.template_id) {
    return
  }
  // 共享过来的工具不让编辑
  if (isShared.value) {
    return
  }
  DataSourceToolDrawertitle.value = data
    ? t('views.tool.dataSource.editDataSource')
    : t('views.tool.dataSource.createDataSource')
  if (data) {
    loadSharedApi({ type: 'tool', systemType: apiType.value })
      .getToolById(data?.id, loading)
      .then((res: any) => {
        DataSourceToolFormDrawerRef.value.open(res.data)
      })
  } else {
    DataSourceToolFormDrawerRef.value.open(data)
  }
}

async function changeState(row: any) {
  if (changeStateloading.value || isShared.value || !permissionPrecise.value.switch(row.id)) return
  changeStateloading.value = true
  const enable = !row.is_active
  try {
    if (!enable) {
      await MsgConfirm(t('views.tool.disabled.confirmTitle') + row.name + '?', t('views.tool.disabled.confirmMessage'), {
        confirmButtonText: t('common.status.disable'), confirmButtonClass: 'danger',
      })
    } else {
      const { data } = await fetchDetail(row.id)
      if (data.tool_type === 'WORKFLOW' && !data.is_publish) {
        await MsgConfirm(t('common.tip'), t('views.tool.toolWorkflow.toActiveTip'))
        toWorkflow(data)
        return
      }
      if (data.init_field_list?.some((field: any) => field.required && !hasStartupValue(data, field))) {
        InitParamDrawerRef.value.open(data, true)
        return
      }
    }
    await loadSharedApi({ type: 'tool', systemType: apiType.value }).putTool(row.id, { is_active: enable })
    tool.setToolList(tool.toolList.map(item => item.id === row.id ? { ...item, is_active: enable } : item))
    await toolStoreDescDrawerRef.value?.reload(row.id)
    MsgSuccess(t(enable ? 'common.status.enableSuccess' : 'common.status.disableSuccess'))
  } catch (error: any) {
    if (error !== 'cancel' && error !== 'close' && !error?.code && !error?.response?.data?.message)
      MsgError(t('views.tool.detail.stateError'))
  } finally {
    changeStateloading.value = false
  }
}

async function copyTool(row: any) {
  // mcp工具
  if (row?.tool_type === 'MCP') {
    bus.emit('select_node', row.folder_id)
    await copyMcpTool(row)
    return
  }
  // 数据源工具
  if (row?.tool_type === 'DATA_SOURCE') {
    bus.emit('select_node', row.folder_id)
    await copyDataSource(row)
    return
  }
  // 技能
  if (row?.tool_type === 'SKILL') {
    bus.emit('select_node', row.folder_id)
    await copySkillTool(row)
    return
  }
  if (row?.tool_type === 'WORKFLOW') {
    workflowFormDialogTitle.value = t('views.tool.toolWorkflow.copyToolWorkflow')
    const res = await loadSharedApi({ type: 'tool', systemType: apiType.value }).getToolById(
      row.id,
      changeStateloading,
    )
    const obj = cloneDeep(res.data)
    delete obj['id']
    obj['name'] = obj['name'] + `  ${t('common.copyTitle')}`
    workflowFormDialogRef.value?.open(obj)
    return
  }
  ToolDrawertitle.value = t('views.tool.copyTool')
  const res = await loadSharedApi({ type: 'tool', systemType: apiType.value }).getToolById(
    row.id,
    changeStateloading,
  )
  const obj = cloneDeep(res.data)
  delete obj['id']
  obj['name'] = obj['name'] + `  ${t('common.copyTitle')}`
  ToolFormDrawerRef.value.open(obj)
}

async function copyMcpTool(row: any) {
  McpToolDrawertitle.value = t('views.tool.mcp.copyMcpTool')
  const res = await loadSharedApi({ type: 'tool', systemType: apiType.value }).getToolById(
    row.id,
    changeStateloading,
  )
  const obj = cloneDeep(res.data)
  delete obj['id']
  obj['name'] = obj['name'] + `  ${t('common.copyTitle')}`
  McpToolFormDrawerRef.value.open(obj)
}

async function copyDataSource(row: any) {
  DataSourceToolDrawertitle.value = t('views.tool.dataSource.copyDataSource')
  const res = await loadSharedApi({ type: 'tool', systemType: apiType.value }).getToolById(
    row.id,
    changeStateloading,
  )
  const obj = cloneDeep(res.data)
  delete obj['id']
  obj['name'] = obj['name'] + `  ${t('common.copyTitle')}`
  DataSourceToolFormDrawerRef.value.open(obj)
}

async function copySkillTool(row: any) {
  SkillToolDrawertitle.value = t('views.tool.skill.copySkillTool')
  const res = await loadSharedApi({ type: 'tool', systemType: apiType.value }).getToolById(
    row.id,
    changeStateloading,
  )
  const obj = cloneDeep(res.data)
  delete obj['id']
  obj['name'] = obj['name'] + `  ${t('common.copyTitle')}`
  SkillToolFormDrawerRef.value.open(obj)
}

function exportTool(row: any) {
  loadSharedApi({ type: 'tool', systemType: apiType.value })
    .exportTool(row.id, row.name, loading)
    .catch((e: any) => {
      if (e.response.status !== 403) {
        e.response.data.text().then((res: string) => {
          MsgError(`${t('views.application.tip.ExportError')}:${JSON.parse(res).message}`)
        })
      }
    })
}

function deleteTool(row: any) {
  MsgConfirm(
    `${t('views.tool.delete.confirmTitle')}：${row.name} ?`,
    row.resource_count > 0 ? t('views.tool.delete.resourceCountMessage', row.resource_count) : '',
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      confirmButtonClass: 'danger',
    },
  )
    .then(() => {
      loadSharedApi({ type: 'tool', systemType: apiType.value })
        .delTool(row.id, loading)
        .then(() => {
          const list = cloneDeep(tool.toolList)
          const index = list.findIndex((v) => v.id === row.id)
          list.splice(index, 1)
          tool.setToolList(list)
          MsgSuccess(t('common.deleteSuccess'))
        })
    })
    .catch(() => {})
}

function configInitParams(item: any) {
  loadSharedApi({ type: 'tool', systemType: apiType.value })
    .getToolById(item?.id, changeStateloading)
    .then((res: any) => {
      InitParamDrawerRef.value.open(res.data)
    })
}

const toolStoreDialogRef = ref<InstanceType<typeof ToolStoreDialog>>()
const targetFolder = computed(() => {
  const id = folder.currentFolder?.id || user.getWorkspaceId()
  return { id, name: i18n_name(folder.currentFolder?.name || id) }
})

function openToolStoreDialog() {
  if (isShared.value || !permissionPrecise.value.create()) return
  const { id, name } = targetFolder.value
  if (id) toolStoreDialogRef.value?.open(id, name)
}

const AddInternalToolDialogRef = ref<InstanceType<typeof AddInternalToolDialog>>()

function addInternalTool(data?: any, isEdit?: boolean) {
  AddInternalToolDialogRef.value?.open(data, isEdit)
}

function confirmAddInternalTool(data?: any, isEdit?: boolean) {
  if (isEdit) {
    loadSharedApi({ type: 'tool', systemType: apiType.value })
      .putTool(data?.id as string, { name: data.name }, loading)
      .then((res: any) => {
        MsgSuccess(t('common.saveSuccess'))
        toolStoreDescDrawerRef.value?.reload(data.id)
        refresh()
      })
  }
}

const storeTools = ref<any[]>([])

function getStoreToolList() {
  ToolStoreApi.getStoreToolList({ name: '' })
    .then((res: any) => {
      storeTools.value = res.data?.apps || []
    })
    .catch(() => {
      storeTools.value = []
    })
}

function showUpdateStoreTool(item: any) {
  return storeTools.value.find(
    (entry) => entry.id === item.template_id && entry.version !== item.version,
  )
}

function updateStoreTool(item: any) {
  const upstream = showUpdateStoreTool(item)
  if (!upstream) return
  MsgConfirm(
    t('views.tool.toolStore.confirmTip') + item.name,
    t('views.tool.toolStore.updateStoreToolMessage'),
    {
      cancelButtonText: t('common.cancel'),
      confirmButtonText: t('common.confirm'),
    },
  )
    .then(() => {
      loadSharedApi({ type: 'tool', systemType: apiType.value })
        .updateStoreTool(item.id, { version: upstream.version }, loading)
        .then(async (res: any) => {
          if (res?.data) {
            refresh()
            return user.profile()
          }
        })
    })
    .catch(() => {})
}

const importDialogRef = ref<InstanceType<typeof ToolImportDialog>>()
function openImport() {
  if (isShared.value || !permissionPrecise.value.import()) return
  const { id, name } = targetFolder.value
  if (id) importDialogRef.value?.open(id, name)
}
async function afterImport(row?: { id: string }) {
  refresh()
  try { await user.profile() } catch { /* The tool is already installed. */ }
  openSaved(row)
}

const McpToolConfigDialogRef = ref()

function showMcpConfig(item: any) {
  loadSharedApi({ type: 'tool', systemType: apiType.value })
    .getToolById(item?.id, loading)
    .then((res: any) => {
      McpToolConfigDialogRef.value.open(res.data)
    })
}

function refresh(data?: any) {
  if (data) {
    if (data.id) toolStoreDescDrawerRef.value?.reload(data.id)
    const list = cloneDeep(tool.toolList)
    const index = list.findIndex((v) => v.id === data.id)
    if (index >= 0) {
      list.splice(index, 1, data)
      tool.setToolList(list)
    } else {
      refresh()
    }
  } else {
    paginationConfig.total = 0
    paginationConfig.current_page = 1
    tool.setToolList([])
    getList()
  }
}

let checkedCatalog = false

// 文件夹相关
const CreateFolderDialogRef = ref()

function openCreateFolder() {
  if (!canCreateFolder.value) return
  CreateFolderDialogRef.value.open(SourceTypeEnum.TOOL, folder.currentFolder.id)
}

watch(
  () => folder.currentFolder?.id,
  (newValue) => {
    if (newValue) {
      batchSelectedHandle(false)
      refresh()
    }
  },
  { immediate: true },
)

watch(
  () => tool.tool_type,
  () => {
    refresh()
  },
)

async function getList() {
  const request = ++listRequest
  const page = paginationConfig.current_page
  listBusy.value = true
  listError.value = false
  const params: any = {
    folder_id: folder.currentFolder?.id || user.getWorkspaceId(),
    scope: apiType.value === 'systemShare' ? 'SHARED' : 'WORKSPACE',
    tool_type: tool.tool_type || '',
  }
  if (search_form.value[search_type.value]) {
    params[search_type.value] = search_form.value[search_type.value]
  }
  try {
    const res = await loadSharedApi({
      type: 'tool',
      isShared: isShared.value,
      systemType: apiType.value,
    }).getToolListPage({ current_page: page, page_size: paginationConfig.page_size }, params)
    if (request !== listRequest) return
    paginationConfig.total = res.data.total
    const merged = new Map<string, any>()
    for (const item of [...(page === 1 ? [] : tool.toolList), ...res.data.records])
      merged.set(item.id, item)
    tool.setToolList([...merged.values()])
    if (!checkedCatalog && res.data.records.some((row: any) => row.template_id)) {
      checkedCatalog = true
      getStoreToolList()
    }
  } catch {
    if (request === listRequest) listError.value = true
  } finally {
    if (request === listRequest) listBusy.value = false
  }
}

function refreshFolder() {
  emit('refreshFolder')
}

function searchHandle() {
  refresh()
}

function getUserList(query: string) {
  let workspaceId = user.getWorkspaceId()
  if (isSystemShare.value) {
    workspaceId = ''
  }
  const actualWorkspaceId = workspaceId || (query ? { nick_name: query } : '')
  const actualQuery = workspaceId ? (query ? { nick_name: query } : '') : undefined

  loadSharedApi({ type: 'workspace', isShared: isShared.value, systemType: apiType.value })
    .getAllMemberList(actualWorkspaceId, actualQuery, loading)
    .then((res: any) => {
      user_options.value = res.data
    })
}

onMounted(() => {
  if (apiType.value !== 'workspace') {
    getList()
  }
})
onBeforeUnmount(() => {
  ++listRequest
})
</script>

<style scoped>
.tool-toolbar,
.tool-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  min-width: 0;
}
.tool-toolbar {
  justify-content: flex-end;
}
.tool-toolbar .ml-8,
.tool-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
.browse-tools {
  color: var(--studio-ink);
  background: var(--studio-selection);
  border-color: var(--studio-hairline);
}
.browse-tools:hover,
.browse-tools:focus-visible {
  border-color: var(--studio-ink);
}
.tool-results {
  min-height: 150px;
  padding: 2px 1px;
}
.tool-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  color: var(--app-text-color-secondary);
}
.tool-library :deep(.content-toolbar) {
  gap: 12px;
}
@media (max-width: 760px) {
  .tool-toolbar,
  .tool-actions {
    width: 100%;
    justify-content: flex-start;
  }
  .tool-toolbar .complex-search {
    flex: 1 1 170px;
    min-width: 0;
  }
  .tool-toolbar .complex-search__left {
    flex: 0 0 90px;
  }
  .tool-toolbar .complex-search > :last-child {
    flex: 1;
    min-width: 0;
  }
  .tool-actions > :deep(.el-button),
  .tool-actions :deep(.el-button) {
    padding-inline: 10px;
  }
}
</style>
