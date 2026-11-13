<template>
  <LayoutContainer showCollapse resizable class="knowledge-manage" :navigation-label="$t('views.knowledge.title')">
    <template #left>
      <h4 class="folder-title">
        <el-icon aria-hidden="true"><FolderOpened /></el-icon>{{ $t('views.knowledge.title') }}
      </h4>

      <FolderVirtualizedTree
        :source="SourceTypeEnum.KNOWLEDGE"
        :data="folderList"
        :currentNodeKey="folder.currentFolder?.id"
        @handleNodeClick="folderClickHandle"
        :showShared="false"
        @refreshTree="refreshFolder"
        :draggable="true"
      />
    </template>
    <KnowledgeListContainer @refreshFolder="refreshFolder">
      <template #header>
        <FolderBreadcrumb :folderList="folderList" @click="folderClickHandle" />
      </template>
    </KnowledgeListContainer>
  </LayoutContainer>
</template>

<script lang="ts" setup>
import { onMounted, ref, computed } from 'vue'
import KnowledgeListContainer from '@/views/knowledge/component/KnowledgeListContainer.vue'
import { SourceTypeEnum } from '@/enums/common'
import { useRoute } from 'vue-router'
import useStore from '@/stores'
const route = useRoute()
const { folder, knowledge } = useStore()
const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})
const loading = ref(false)

const folderList = ref<any[]>([])

function getFolder(bool?: boolean) {
  const params = {}
  folder
    .asyncGetFolder(SourceTypeEnum.KNOWLEDGE, params, apiType.value, loading)
    .then((res: any) => {
      folderList.value = res.data
      if (bool) {
        // 初始化刷新
        folder.setCurrentFolder(res.data?.[0] || {})
      }
    })
}

function folderClickHandle(row: any) {
  if (row.id === folder.currentFolder?.id) {
    return
  }
  folder.setCurrentFolder(row)
  knowledge.setKnowledgeList([])
}

function refreshFolder() {
  getFolder()
}

onMounted(() => {
  getFolder(folder.currentFolder?.id ? false : true)
})
</script>

<style lang="scss" scoped>
.folder-title {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 22px 16px 0;
  color: var(--studio-ink);
  font-weight: 650;
}
.knowledge-manage :deep(.tree-node:has(.maxkb-tree-node.is-current)) {
  color: var(--studio-ink);
  background: var(--studio-selection);
  box-shadow: inset 3px 0 var(--studio-ink);
}
@media (max-width: 760px) {
  .folder-title { display: none; }
  .knowledge-manage :deep(.folder-tree__main) { max-height: 24dvh; }
}
</style>
