<template>
  <LayoutContainer
    showCollapse
    resizable
    class="tool-manage"
    :navigation-label="$t('views.tool.library.folders')"
  >
    <template #left>
      <h4 class="folder-title">
        <el-icon aria-hidden="true"><FolderOpened /></el-icon>{{ $t('views.tool.library.folders') }}
      </h4>

      <FolderVirtualizedTree
        :source="SourceTypeEnum.TOOL"
        :data="folderList"
        :currentNodeKey="folder.currentFolder?.id"
        @handleNodeClick="folderClickHandle"
        :showShared="false"
        @refreshTree="refreshFolder"
        :draggable="true"
      />
    </template>
    <div v-if="(folderError || !loading) && !folderList.length" class="folder-error" role="alert">
      {{ $t('views.tool.library.folderError') }}
      <el-button @click="refreshFolder">{{ $t('views.tool.library.retry') }}</el-button>
    </div>
    <div v-else-if="loading && !folderList.length" class="folder-error" aria-busy="true">
      <ListPlaceholder class="folder-placeholder" />
    </div>
    <ToolListContainer v-else-if="folderList.length" @refreshFolder="refreshFolder">
      <template #header>
        <div class="folder-heading">
          <FolderBreadcrumb :folderList="folderList" @click="folderClickHandle" />
          <el-select
            v-model="toolType"
            class="type-filter"
            :aria-label="$t('common.type')"
            @change="radioChange"
            :empty-values="[null, undefined]"
            :value-on-clear="null"
          >
            <el-option :label="$t('views.tool.library.allTypes')" value="" />
            <el-option :label="$t('views.tool.title')" value="CUSTOM" />
            <el-option label="Skills" value="SKILL" />
            <el-option :label="$t('workflow.workflow')" value="WORKFLOW" />
            <el-option label="MCP" value="MCP" />
            <el-option :label="$t('views.tool.dataSource.title')" value="DATA_SOURCE" />
          </el-select>
        </div>
      </template>
    </ToolListContainer>
  </LayoutContainer>
</template>

<script lang="ts" setup>
import ListPlaceholder from '@/components/ListPlaceholder.vue'
import { onBeforeUnmount, onMounted, ref, computed } from 'vue'
import { FolderOpened } from '@element-plus/icons-vue'
import ToolListContainer from '@/views/tool/component/ToolListContainer.vue'
import { SourceTypeEnum } from '@/enums/common'
import { TreeToFlatten } from '@/utils/array'
import { useRoute } from 'vue-router'
import useStore from '@/stores'
const route = useRoute()
const { folder, tool } = useStore()

const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})
const loading = ref(true)
const toolType = ref('')
const folderError = ref(false)

const folderList = ref<any[]>([])

let folderRequest = 0
async function refreshFolder() {
  const request = ++folderRequest
  folderError.value = false
  try {
    const res = (await folder.asyncGetFolder(SourceTypeEnum.TOOL, {}, apiType.value, loading)) as {
      data: any[]
    }
    if (request !== folderRequest) return
    folderList.value = res.data
    const selected = TreeToFlatten(res.data).find((row: any) => row.id === folder.currentFolder?.id)
    folder.setCurrentFolder(selected || res.data[0] || {})
  } catch {
    if (request === folderRequest) folderError.value = true
  }
}

function folderClickHandle(row: any) {
  if (row.id === folder.currentFolder?.id) {
    return
  }
  folder.setCurrentFolder(row)
  tool.setToolList([])
}

function radioChange() {
  tool.setToolType(toolType.value)
}

onMounted(() => {
  refreshFolder()
  radioChange()
})
onBeforeUnmount(() => {
  ++folderRequest
})
</script>

<style scoped>
.folder-placeholder { width: 100%; }
.folder-title,
.folder-heading,
.folder-error {
  display: flex;
  align-items: center;
  gap: 10px;
}
.folder-title {
  padding: 22px 16px 0;
  color: var(--studio-ink);
  font-weight: 650;
}
.folder-heading {
  flex-wrap: wrap;
  min-width: 0;
}
.folder-heading :deep(.el-breadcrumb) {
  min-width: 0;
  overflow-wrap: anywhere;
}
.type-filter {
  width: 116px;
  max-width: 100%;
}
.folder-error {
  padding: 24px;
  color: var(--app-text-color-secondary);
}
.tool-manage :deep(.tree-node:has(.maxkb-tree-node.is-current)) {
  color: var(--studio-ink);
  background: var(--studio-selection);
}
@media (max-width: 760px) {
  .folder-title {
    display: none;
  }
  .tool-manage :deep(.folder-tree__main) {
    max-height: 24dvh;
  }
}
</style>
