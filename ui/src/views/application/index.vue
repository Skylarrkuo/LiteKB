<template>
  <LayoutContainer showCollapse resizable class="application-manage" :navigation-label="$t('views.application.folders')">
    <template #left>
      <h3 class="folder-heading">{{ $t('views.application.folders') }}</h3>

      <FolderVirtualizedTree
        :source="SourceTypeEnum.APPLICATION"
        :data="folderList"
        :currentNodeKey="folder.currentFolder?.id"
        @handleNodeClick="folderClickHandle"
        @refreshTree="refreshFolder"
        :draggable="true"
      />
    </template>
    <ContentContainer>
      <template #header>
        <div class="agent-heading">
          <FolderBreadcrumb :folderList="folderList" @click="folderClickHandle" />
          <span v-if="!loading && !listLoading && !listFailed" class="agent-count">{{ paginationConfig.total }}</span>
        </div>
      </template>
      <template #search>
        <div class="agent-controls">
          <div class="complex-search">
            <el-select
              class="complex-search__left"
              v-model="search_type"
              :aria-label="$t('views.application.searchField')"
              @change="search_type_change"
            >
              <el-option :label="$t('common.creator')" value="create_user" />

              <el-option :label="$t('common.name')" value="name" />

              <el-option :label="$t('views.application.publishStatus')" value="publish_status" />
            </el-select>
            <el-input
              v-if="search_type === 'name'"
              v-model="search_form.name"
              :aria-label="$t('common.searchBar.placeholder')"
              @input="scheduleSearch"
              @keyup.enter="commitNameSearch"
              @clear="searchHandle"
              :placeholder="$t('common.searchBar.placeholder')"
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
            >
              <el-option v-for="u in user_options" :key="u.id" :value="u.id" :label="u.nick_name" />
            </el-select>
            <el-select
              v-else-if="search_type === 'publish_status'"
              v-model="search_form.publish_status"
              :aria-label="$t('views.application.publishStatus')"
              @change="searchHandle"
              filterable
              clearable
            >
              <el-option :label="$t('common.status.published')" value="published" />
              <el-option :label="$t('common.status.unpublished')" value="unpublished" />
            </el-select>
          </div>
          <span
            v-if="
              permissionPrecise.batchDelete() ||
              permissionPrecise.batchMove() ||
              permissionPrecise.batchCleanStrategy()
            "
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
          <div v-if="!isBatch && permissionPrecise.create()" class="agent-create-actions">
            <el-button type="primary" class="agent-create" @click="openCreateDialog()">
              <AppIcon iconName="app-add-outlined" class="mr-4" />
              {{ $t('views.application.createAgent') }}
            </el-button>
            <el-dropdown trigger="click">
              <el-button class="agent-more-create" :aria-label="$t('common.moreSettings')" :title="$t('common.moreSettings')">
                <AppIcon iconName="app-more" />
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="agentImport?.click()">
                    <el-icon><Upload /></el-icon> {{ $t('views.application.importApplication') }}
                  </el-dropdown-item>
                  <el-dropdown-item v-if="permissionPrecise.folderCreate(folder.currentFolder?.id || 'default')" @click="openCreateFolder">
                    <AppIcon iconName="app-folder" /> {{ $t('components.folder.addFolder') }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <input ref="agentImport" type="file" hidden @change="importApplication" />
          </div>
        </div>
      </template>
      <div class="agent-results" :aria-busy="loading || listLoading" v-loading="loading && applicationList.length > 0">
        <InfiniteScroll
          :size="applicationList.length"
          :total="listFailed ? 0 : paginationConfig.total"
          :page_size="paginationConfig.page_size"
          v-model:current_page="paginationConfig.current_page"
          @load="getList"
          :loading="listLoading"
        >
          <div v-if="applicationList.length" class="agent-grid studio-result-enter">
            <article v-for="item in applicationList" :key="item.id" class="agent-card" :class="{ selected: multipleSelection.includes(item.id) }">
              <div class="agent-card-heading">
                <img class="agent-icon" :src="isAppIcon(resetUrl(item.icon)) || brandIcon" alt="" />
                <div class="agent-identity">
                  <h3>
                    <label v-if="isBatch" :for="'select-agent-' + item.id">{{ item.name }}</label>
                    <RouterLink v-else class="agent-link" :to="get_route(item)" :title="item.name">{{ item.name }}</RouterLink>
                  </h3>
                  <span>{{ i18n_name(item.nick_name) }} · {{ dateFormat(item.create_time) }}</span>
                </div>
                <input
                  v-if="isBatch" type="checkbox" class="agent-check"
                  :id="'select-agent-' + item.id" :value="item.id" v-model="multipleSelection"
                  :aria-label="item.name"
                />
                <span v-else class="agent-kind" :class="{ 'is-workflow': isWorkFlow(item.type) }">
                  {{ isWorkFlow(item.type) ? $t('views.application.workflowShort') : $t('views.application.simple') }}
                </span>
              </div>
              <p class="agent-description">{{ item.desc }}</p>
              <footer class="agent-card-footer">
                <div class="agent-publication" :class="{ published: item.is_publish }">
                  <i aria-hidden="true"></i>
                  {{ item.is_publish ? $t('common.status.published') : $t('common.status.unpublished') }}
                  <time v-if="item.is_publish" :datetime="item.update_time">{{ dateFormat(item.update_time) }}</time>
                </div>
                <el-dropdown trigger="click" v-if="!isBatch && canManage(item.id)">
                  <el-button class="agent-card-menu" text :aria-label="item.name + ' · ' + $t('common.moreSettings')">
                    <AppIcon iconName="app-more" />
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item v-if="permissionPrecise.edit(item.id)" @click="settingApplication($event, item)">
                        <AppIcon iconName="app-setting" class="color-secondary" />
                        {{ $t('common.setting') }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        @click.stop="openAuthorization(item)"
                        v-if="permissionPrecise.auth(item.id)"
                      >
                        <AppIcon
                          iconName="app-resource-authorization"
                          class="color-secondary"
                        ></AppIcon>
                        {{ $t('views.system.resourceAuthorization.title') }}
                      </el-dropdown-item>
                      <el-dropdown-item
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
                        @click.stop="openMoveToDialog(item)"
                        v-if="permissionPrecise.edit(item.id) && apiType === 'workspace'"
                      >
                        <AppIcon iconName="app-migrate" class="color-secondary"></AppIcon>
                        {{ $t('common.moveTo') }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        @click="copyApplication(item)"
                        v-if="permissionPrecise.copy(item.id)"
                      >
                        <AppIcon iconName="app-copy" class="color-secondary"></AppIcon>
                        {{ $t('common.copy') }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        divided
                        @click.stop="exportApplication(item)"
                        v-if="permissionPrecise.export(item.id)"
                      >
                        <AppIcon iconName="app-export" class="color-secondary"></AppIcon>
                        {{ $t('common.export') }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        divided
                        @click.stop="deleteApplication(item)"
                        v-if="permissionPrecise.delete(item.id)"
                      >
                        <AppIcon iconName="app-delete" class="color-secondary"></AppIcon>
                        {{ $t('common.delete') }}
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </footer>
            </article>
          </div>
          <ListPlaceholder v-else-if="loading || listLoading" />
          <div v-else-if="!listLoading && !loading && !listFailed" class="agent-empty">
            <span aria-hidden="true" class="empty-mark"><el-icon v-if="activeFilter"><Search /></el-icon><AppIcon v-else iconName="app-agent" /></span>
            <h3>{{ activeFilter ? $t('views.application.noMatch') : $t('views.application.emptyFolder') }}</h3>
            <el-button v-if="activeFilter" link type="primary" @click="resetFilters">{{ $t('views.application.clearFilter') }}</el-button>
          </div>
        </InfiniteScroll>
        <div v-if="listFailed" class="agent-retry" role="status">
          <span>{{ $t('views.application.loadFailed') }}</span>
          <el-button link type="primary" @click="getList">{{ $t('common.refresh') }}</el-button>
        </div>
      </div>
      <!-- 批量操作拦 -->
      <div class="agent-batch" v-if="isBatch">
        <el-checkbox
          :model-value="checkAll"
          :indeterminate="isIndeterminate"
          @change="handleCheckAllChange"
        >
          {{ $t('views.application.selectLoaded') }}
        </el-checkbox>
        <el-button
          :disabled="multipleSelection.length === 0"
          @click="openMoveToDialog()"
          v-if="permissionPrecise.batchMove()"
        >
          {{ $t('common.moveTo') }}
        </el-button>

        <el-button
          :disabled="multipleSelection.length === 0"
          @click="openBatchClearStrategyDialog"
          v-if="permissionPrecise.batchCleanStrategy()"
        >
          {{ $t('views.chatLog.buttons.clearStrategy') }}
        </el-button>

        <el-button
          :disabled="multipleSelection.length === 0"
          @click="deleteMulApplication"
          v-if="permissionPrecise.batchDelete()"
        >
          {{ $t('common.delete') }}
        </el-button>
        <span role="status" class="batch-count">
          {{ $t('common.selected') }} {{ multipleSelection.length }} / {{ paginationConfig.total }}
          {{ $t('views.document.items') }}
        </span>
      </div>
    </ContentContainer>
    <ResourceMappingDrawer ref="resourceMappingDrawerRef" />
    <CreateApplicationDialog ref="CreateApplicationDialogRef" @refresh="searchHandle" />
    <CopyApplicationDialog ref="CopyApplicationDialogRef" />
    <BatchClearStrategyDialog ref="BatchClearStrategyDialogRef" @refresh="refreshApplicationList()" />
    <CreateFolderDialog ref="CreateFolderDialogRef" @refresh="refreshFolder" />
    <MoveToDialog
      ref="MoveToDialogRef"
      :source="SourceTypeEnum.APPLICATION"
      @refresh="refreshApplicationList"
      v-if="apiType === 'workspace'"
    />
    <ResourceAuthorizationDrawer
      :type="SourceTypeEnum.APPLICATION"
      ref="ResourceAuthorizationDrawerRef"
    />

  </LayoutContainer>
</template>

<script lang="ts" setup>
import ListPlaceholder from '@/components/ListPlaceholder.vue'
import { onBeforeUnmount, onMounted, ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { CheckboxValueType } from 'element-plus'
import CreateApplicationDialog from '@/views/application/component/CreateApplicationDialog.vue'
import CreateFolderDialog from '@/components/folder-virtualized-tree/CreateFolderDialog.vue'
import CopyApplicationDialog from '@/views/application/component/CopyApplicationDialog.vue'
import BatchClearStrategyDialog from '@/views/application/component/BatchClearStrategyDialog.vue'
import MoveToDialog from '@/components/folder-virtualized-tree/MoveToDialog.vue'
import ResourceAuthorizationDrawer from '@/components/resource-authorization-drawer/index.vue'
import ApplicationApi from '@/api/application/application'
import WorkspaceApi from '@/api/workspace/workspace'
import { MsgSuccess, MsgConfirm, MsgError } from '@/utils/message'
import { i18n_name, isAppIcon, resetUrl } from '@/utils/common'
import { TreeToFlatten } from '@/utils/array'
import { isWorkFlow } from '@/utils/application'
import { dateFormat } from '@/utils/time'
import { SourceTypeEnum } from '@/enums/common'
import permissionMap from '@/permission'
import { hasPermission } from '@/utils/permission'
import { ComplexPermission } from '@/utils/permission/type'
import { PermissionConst, RoleConst } from '@/utils/permission/data'
import ResourceMappingDrawer from '@/components/resource_mapping/index.vue'
import useStore from '@/stores'
import { t } from '@/locales'
import { brandIcon } from '@/utils/branding'

const router = useRouter()

const apiType = computed<'workspace'>(() => {
  return 'workspace'
})
const permissionPrecise = computed(() => {
  return permissionMap['application'][apiType.value]
})

const { folder, user } = useStore()

const loading = ref(false)
const listLoading = ref(false)
const listFailed = ref(false)
let listRevision = 0
let memberRevision = 0
let searchTimer: ReturnType<typeof setTimeout> | undefined

const search_type = ref('name')
const search_form = ref<any>({
  name: '',
  create_user: '',
  publish_status: undefined,
})

const activeFilter = computed(() => Boolean(search_form.value[search_type.value]))
const user_options = ref<any[]>([])

const paginationConfig = reactive({
  current_page: 1,
  page_size: 30,
  total: 0,
})

const folderList = ref<any[]>([])
const applicationList = ref<any[]>([])
const CopyApplicationDialogRef = ref()
const BatchClearStrategyDialogRef = ref<InstanceType<typeof BatchClearStrategyDialog>>()

// 批量操作
const isBatch = ref(false)
const multipleSelection = ref<string[]>([])
const checkAll = computed(() => applicationList.value.length > 0 && multipleSelection.value.length === applicationList.value.length)
const isIndeterminate = computed(() => {
  return (
    multipleSelection.value.length > 0 &&
    multipleSelection.value.length < applicationList.value.length
  )
})

function batchSelectedHandle(bool: boolean) {
  isBatch.value = bool
  multipleSelection.value = []
}

const handleCheckAllChange = (val: CheckboxValueType) => {
  multipleSelection.value = val ? applicationList.value.map((item) => item.id) : []
}

function canManage(id: string) {
  const p = permissionPrecise.value
  return p.edit(id) || p.auth(id) || p.relate_map(id) || p.copy(id) || p.export(id) || p.delete(id)
}

function deleteMulApplication() {
  const selectedIds = [...multipleSelection.value]
  MsgConfirm(
    `${t('views.document.delete.confirmTitle1')} ${selectedIds.length} ${t('views.application.delete.confirmTitle2')}`,
    t('views.paragraph.delete.confirmMessage'),
    {
      confirmButtonText: t('common.confirm'),
      confirmButtonClass: 'danger',
    },
  )
    .then(() => {
      ApplicationApi.delMulApplication(selectedIds, loading).then(() => {
        batchSelectedHandle(false)
        searchHandle()
        MsgSuccess(t('views.document.delete.successMessage'))
      })
    })
    .catch(() => {})
}

function openBatchClearStrategyDialog() {
  BatchClearStrategyDialogRef.value?.open([...multipleSelection.value])
}


const resourceMappingDrawerRef = ref<InstanceType<typeof ResourceMappingDrawer>>()
const openResourceMappingDrawer = (data: any) => {
  resourceMappingDrawerRef.value?.open('APPLICATION', data)
}

const ResourceAuthorizationDrawerRef = ref()

function openAuthorization(item: any) {
  ResourceAuthorizationDrawerRef.value.open(item.id)
}

const MoveToDialogRef = ref()

function openMoveToDialog(data?: any) {
  let obj
  if (isBatch.value) {
    obj = {
      id_list: multipleSelection.value,
    }
  } else {
    // 仅2个参数就行
    obj = {
      id: data.id,
      folder_id: data.folder,
    }
  }

  MoveToDialogRef.value?.open(obj)
}

function refreshApplicationList() {
  batchSelectedHandle(false)
  searchHandle()
}

const get_route = (item: any) => {
  if (
    hasPermission(
      [
        new ComplexPermission(
          [RoleConst.USER],
          [PermissionConst.APPLICATION.getApplicationWorkspaceResourcePermission(item.id)],
          [],
          'AND',
        ),
        RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
        PermissionConst.APPLICATION_OVERVIEW_READ.getWorkspacePermissionWorkspaceManageRole,
        PermissionConst.APPLICATION_OVERVIEW_READ.getApplicationWorkspaceResourcePermission(
          item.id,
        ),
      ],
      'OR',
    )
  ) {
    return `/application/workspace/${item.id}/${item.type}/overview`
  } else if (
    hasPermission(
      [
        new ComplexPermission(
          [RoleConst.USER],
          [PermissionConst.APPLICATION.getApplicationWorkspaceResourcePermission(item.id)],
          [],
          'AND',
        ),
        RoleConst.WORKSPACE_MANAGE.getWorkspaceRole,
        PermissionConst.APPLICATION_EDIT.getWorkspacePermissionWorkspaceManageRole,
        PermissionConst.APPLICATION_EDIT.getApplicationWorkspaceResourcePermission(item.id),
      ],
      'OR',
    )
  ) {
    if (item.type == 'WORK_FLOW') {
      return `/application/workspace/${item.id}/workflow`
    } else {
      return `/application/workspace/${item.id}/${item.type}/setting`
    }
  } else if (
    hasPermission(
      [
        new ComplexPermission(
          [RoleConst.USER],
          [PermissionConst.APPLICATION.getApplicationWorkspaceResourcePermission(item.id)],
          [],
          'AND',
        ),
        PermissionConst.APPLICATION_CHAT_LOG_READ.getWorkspacePermissionWorkspaceManageRole,
        PermissionConst.APPLICATION_CHAT_LOG_READ.getApplicationWorkspaceResourcePermission(
          item.id,
        ),
      ],
      'OR',
    )
  ) {
    return `/application/workspace/${item.id}/${item.type}/chat-log`
  } else return `/application/`
}

const CreateApplicationDialogRef = ref()

function openCreateDialog(type?: string) {
  CreateApplicationDialogRef.value.open(folder.currentFolder?.id || 'default', type)
}

function resetFilters() {
  search_form.value = { name: '', create_user: '', publish_status: undefined }
  searchHandle()
}
function search_type_change() {
  resetFilters()
}



function copyApplication(row: any) {
  ApplicationApi.getApplicationDetail(row.id, loading).then((res: any) => {
    if (res?.data) {
      CopyApplicationDialogRef.value.open(
        { ...res.data, model_id: res.data.model },
        folder.currentFolder?.id || 'default',
      )
    }
  })
}

function settingApplication(event: any, row: any) {
  if (isWorkFlow(row.type)) {
    if (event?.ctrlKey) {
      event?.preventDefault()
      event.stopPropagation()
      const newUrl = router.resolve({
        path: `/application/workspace/${row.id}/workflow`,
      }).href
      window.open(newUrl)
    } else {
      router.push({ path: `/application/workspace/${row.id}/workflow` })
    }
  } else {
    router.push({ path: `/application/workspace/${row.id}/${row.type}/setting` })
  }
}

function deleteApplication(row: any) {
  MsgConfirm(
    `${t('views.application.delete.confirmTitle')}${row.name} ?`,
    row.resource_count > 0
      ? t('views.application.delete.resourceCountMessage', row.resource_count)
      : '',
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      confirmButtonClass: 'danger',
    },
  )
    .then(() => {
      ApplicationApi.delApplication(row.id, loading).then(() => {
        searchHandle()
        MsgSuccess(t('common.deleteSuccess'))
      })
    })
    .catch(() => {})
}

const exportApplication = (application: any) => {
  ApplicationApi.exportApplication(application.id, application.name, loading).catch((e) => {
    if (e.response.status !== 403) {
      e.response.data.text().then((res: string) => {
        MsgError(`${t('views.application.tip.ExportError')}:${JSON.parse(res).message}`)
      })
    }
  })
}

const agentImport = ref<HTMLInputElement>()
async function importApplication(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  input.value = ''
  const formData = new FormData()
  formData.append('file', file, file.name)
  await ApplicationApi.importApplication(folder.currentFolder?.id || 'default', formData, loading)
  await user.profile()
  searchHandle()
}

// 文件夹相关
const CreateFolderDialogRef = ref()

function openCreateFolder() {
  CreateFolderDialogRef.value.open(SourceTypeEnum.APPLICATION, folder.currentFolder?.id || 'default')
}

function getFolder(bool?: boolean) {
  const params = {}
  folder
    .asyncGetFolder(SourceTypeEnum.APPLICATION, params, apiType.value, loading)
    .then((res: any) => {
      folderList.value = res.data

      if (bool || !TreeToFlatten(res.data || []).some((node: any) => node.id === folder.currentFolder?.id)) {
        // 初始化刷新
        folder.setCurrentFolder(res.data?.[0] || {})
      }
      searchHandle()
    })
}

function folderClickHandle(row: any) {
  if (row.id === folder.currentFolder?.id) {
    return
  }
  batchSelectedHandle(false)
  folder.setCurrentFolder(row)
  searchHandle()
}

function refreshFolder() {
  getFolder()
}

function scheduleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(searchHandle, 250)
}
function commitNameSearch(event: KeyboardEvent) {
  if (!event.isComposing) searchHandle()
}

function searchHandle() {
  clearTimeout(searchTimer)
  multipleSelection.value = []
  paginationConfig.current_page = 1
  paginationConfig.total = 0
  applicationList.value = []
  getList()
}

async function getList() {
  const version = ++listRevision
  const page = { ...paginationConfig }
  const value = search_form.value[search_type.value]
  const params = {
    folder_id: folder.currentFolder?.id || 'default',
    ...(value ? { [search_type.value]: value } : {}),
  }
  listLoading.value = true
  listFailed.value = false
  try {
    const { data } = await ApplicationApi.getApplication(page, params)
    if (version !== listRevision) return
    paginationConfig.total = data.total
    applicationList.value = page.current_page === 1 ? data.records : [...applicationList.value, ...data.records]
  } catch {
    if (version === listRevision) listFailed.value = true
  } finally {
    if (version === listRevision) listLoading.value = false
  }
}

async function getUserList(query: string) {
  const version = ++memberRevision
  const { data } = await WorkspaceApi.getAllMemberList(user.getWorkspaceId(), query ? { nick_name: query } : '')
  if (version === memberRevision) user_options.value = data
}

onMounted(() => {
  getFolder(!folder.currentFolder?.id)
})
onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  ++listRevision
  ++memberRevision
})
</script>

<style lang="scss" scoped>
.application-manage {
  .folder-heading { margin: 0; padding: 20px 16px 12px; font-size: 15px; }
  :deep(.content-scroll .el-scrollbar__view) { min-height: 100%; }
}
.agent-heading, .agent-controls, .agent-create-actions, .agent-publication, .agent-batch {
  display: flex; align-items: center; gap: 8px; min-width: 0;
}
.agent-heading { flex-wrap: wrap; > :deep(h2) { max-width: min(14em, 70vw); } }
.agent-count, .agent-kind {
  display: inline-block; padding: 3px 8px; border-radius: 7px;
  background: var(--app-layout-bg-color); color: var(--app-text-color-secondary);
  font-size: 12px; line-height: 16px;
}
.agent-count { border-radius: 99px; font-variant-numeric: tabular-nums; }
.agent-controls {
  flex-wrap: wrap;
  .complex-search {
    display: grid; grid-template-columns: 106px minmax(120px, 190px);
    min-width: 0; background: var(--app-view-bg-color);
    :deep(.el-input), :deep(.el-select) { width: 100%; min-width: 0; }
  }
}
.agent-create-actions { gap: 3px; }
.agent-more-create { padding: 6px; }
.agent-results { min-height: 135px; }
.agent-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr)); gap: 14px; }
.agent-card {
  position: relative; display: flex; flex-direction: column; min-width: 0;
  border: 1px solid var(--studio-hairline); border-radius: var(--app-border-radius-large);
  background: var(--app-view-bg-color);
  &:hover, &:focus-within { border-color: var(--el-border-color-hover); }
  &.selected { border-color: var(--studio-ink); background: var(--studio-selection); }
}
.agent-card-heading { display: flex; align-items: flex-start; gap: 10px; padding: 16px 16px 0; }
.agent-icon { flex: none; width: 36px; height: 36px; object-fit: contain; border-radius: 10px; }
.agent-identity {
  flex: 1; min-width: 0;
  h3 { margin: 0; font-size: 16px; line-height: 1.4; }
  h3 a, h3 label, > span { display: block; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }
  h3 a, h3 label { color: var(--studio-ink); font-weight: 650; cursor: pointer; }
  > span { margin-top: 2px; color: var(--app-text-color-secondary); font-size: 12px; }
}
.agent-link::after, .agent-identity label::after { content: ''; position: absolute; inset: 0; border-radius: var(--app-border-radius-large); }
.agent-link:focus-visible { outline: none !important; }
.agent-link:focus-visible::after { outline: 2px solid var(--studio-ink); outline-offset: -2px; }
.agent-kind { flex: none; }
.agent-kind.is-workflow { background: var(--studio-selection); color: var(--studio-ink); }
.agent-check { position: relative; z-index: 1; width: 17px; height: 17px; margin: 1px 0; accent-color: var(--studio-ink); }
.agent-description { margin: 12px 16px; min-height: 40px; color: var(--app-text-color-secondary); font-size: 13px; line-height: 20px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
.agent-card-footer { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-top: auto; padding: 7px 12px 7px 16px; min-height: 30px; border-top: 1px solid var(--studio-hairline); }
.agent-publication {
  font-size: 12px; color: var(--app-text-color-secondary); flex-wrap: wrap;
  i { width: 7px; height: 7px; border-radius: 100%; background: var(--el-text-color-placeholder); }
  &.published i { background: var(--el-color-success); }
  time { padding-left: 8px; border-left: 1px solid var(--studio-hairline); }
}
.agent-card-menu { position: relative; z-index: 1; width: 32px; height: 30px; padding: 0; }
.agent-empty, .agent-retry { display: grid; place-content: center; justify-items: center; gap: 12px; min-height: clamp(220px, 40vh, 380px); border: 1px solid var(--studio-hairline); border-radius: var(--app-border-radius-large); background: var(--app-view-bg-color); text-align: center; }
.agent-empty h3 { margin: 0; font-size: 15px; color: var(--el-text-color-regular); }
.empty-mark { display: grid; place-items: center; width: 50px; height: 50px; border-radius: 14px; background: var(--studio-selection); color: var(--studio-ink); font-size: 24px; }
.agent-retry { min-height: 100px; }
.agent-batch {
  position: sticky; bottom: 0; z-index: 2; flex-wrap: wrap; margin: 12px 0 0; padding: 10px 12px; border: 1px solid var(--studio-hairline); border-radius: 12px; box-shadow: var(--studio-shadow); background: var(--app-view-bg-color);
  :deep(.el-button), :deep(.el-checkbox) { margin: 0; }
}
.batch-count { margin-left: auto; font-size: 12px; color: var(--app-text-color-secondary); }
@media (max-width: 760px) {
  .agent-controls { width: 100%; }
  .agent-controls .complex-search { flex: 1 1 100%; grid-template-columns: 106px minmax(0, 1fr); }
  .agent-create-actions { margin-left: auto; }
  .agent-grid { gap: 10px; }
}
</style>
