<template>
  <div class="paragraph">
    <header class="paragraph-heading">
    <div class="document-title">
      <back-button to="-1" style="margin-left: -4px"></back-button>
      <h2 :title="documentDetail?.name">{{ documentDetail?.name }}</h2>
      <el-text type="info" v-if="documentDetail?.type == 1"
        >（{{ $t('views.document.form.source_url.label') }}：<el-link
          :href="documentDetail?.meta?.source_url"
          target="_blank"
        >
          <span class="break-all">{{ documentDetail?.meta?.source_url }} </span></el-link
        >）
      </el-text>
    </div>
    <div class="header-button" v-if="!shareDisabled && permissionPrecise.doc_edit(id)">
      <el-button @click="batchSelectedHandle(true)" v-if="isBatch === false">
        {{ $t('views.paragraph.setting.batchSelected') }}
      </el-button>
      <el-button @click="batchSelectedHandle(false)" v-if="isBatch === true">
        {{ $t('views.paragraph.setting.cancelSelected') }}
      </el-button>
      <el-button @click="addParagraph" type="primary" :disabled="loading" v-if="isBatch === false">
        {{ $t('views.paragraph.addParagraph') }}
      </el-button>
    </div>
    </header>
    <el-card shadow="never"
      class="paragraph__main"
      v-loading="(paginationConfig.current_page === 1 && loading) || changeStateloading"
    >
      <div class="paragraph-filter">
        <span>{{ paginationConfig.total }} {{ $t('views.paragraph.paragraph_count') }}</span>
        <el-input
          v-model="search"
          :placeholder="$t('common.search')"
          class="input-with-select"
          :aria-label="$t('common.search')"
          @change="searchHandle"
          clearable
        >
          <template #prepend>
            <el-select
              v-model="searchType"
              placeholder="Select"
              style="width: 80px"
              @change="searchTypeChange"
            >
              <el-option :label="$t('common.title')" value="title" />
              <el-option :label="$t('common.content')" value="content" />
            </el-select>
          </template>
        </el-input>
      </div>
      <LayoutContainer showCollapse :navigation-label="$t('views.paragraph.title')">
        <template #left>
          <div class="paragraph-sidebar p-16">
            <el-scrollbar class="paragraph-scrollbar">
              <el-anchor
                direction="vertical"
                type="default"
                :offset="12"
                container=".paragraph-reader .el-scrollbar__wrap"
                @click="handleClick"
              >
                <template v-for="item in paragraphDetail" :key="item.id">
                  <el-anchor-link :href="`#m${item.id}`" :title="item.title" v-if="item.title">
                    <span :title="item.title">
                      {{ item.title }}
                    </span>
                  </el-anchor-link>
                </template>
              </el-anchor>
            </el-scrollbar>
          </div>
        </template>
        <div class="paragraph-reader">
          <el-empty v-if="paragraphDetail.length == 0" :description="$t('common.noData')" />
          <el-scrollbar v-else class="paragraph-scrollbar">
              <div class="paragraph-detail">
                <el-checkbox-group v-model="multipleSelection">
                  <InfiniteScroll
                    :size="paragraphDetail.length"
                    :total="paginationConfig.total"
                    :page_size="paginationConfig.page_size"
                    v-model:current_page="paginationConfig.current_page"
                    @load="getParagraphList"
                    :loading="loading"
                  >
                    <VueDraggable
                      ref="el"
                      v-model="paragraphDetail"
                      :disabled="
                        isBatch === true ||
                        shareDisabled ||
                        dialogVisible ||
                        !permissionPrecise.doc_edit(id)
                      "
                      handle=".handle-img"
                      :animation="150"
                      ghostClass="ghost"
                      @end="onEnd"
                    >
                      <template v-for="(item, index) in paragraphDetail" :key="item.id">
                        <div :id="`m${item.id}`" class="flex mb-16">
                          <!-- 批量操作 -->
                          <div class="paragraph-card flex w-full" v-if="isBatch === true">
                            <el-checkbox :value="item.id" :aria-label="item.title || $t('views.paragraph.title')" />
                            <ParagraphCard
                              :data="item"
                              class="mb-8 w-full"
                              :class="{
                                'is-selected': multipleSelection.includes(item.id),
                              }"
                              :disabled="true"
                              @clickCard="toggleSelect(item.id)"
                            />
                          </div>
                          <!-- 非批量操作 -->
                          <div class="handle paragraph-card flex w-full" :id="item.id" v-else>
                            <img
                              v-if="!shareDisabled && permissionPrecise.doc_edit(id)"
                              src="@/assets/sort.svg"
                              alt=""
                              height="15"
                              class="handle-img mr-8 mt-24 cursor"
                            />

                            <ParagraphCard
                              :data="item"
                              :showMoveUp="index !== 0"
                              :showMoveDown="index < paragraphDetail.length - 1"
                              class="mb-8 w-full"
                              @changeState="changeState"
                              @deleteParagraph="deleteParagraph"
                              @move="
                                (val: string) =>
                                  onEnd(
                                    null,
                                    {
                                      paragraph_id: item.id,
                                      new_position: setPosition(val, index),
                                      target_index: setTargetIndex(val, index),
                                    },
                                    index,
                                  )
                              "
                              @refresh="refresh"
                              @refreshMigrateParagraph="refreshMigrateParagraph"
                              :disabled="shareDisabled"
                              @dialogVisibleChange="dialogVisibleChange"
                            />
                          </div>
                        </div>
                      </template>
                    </VueDraggable>
                  </InfiniteScroll>
                </el-checkbox-group>
              </div>
          </el-scrollbar>
        </div>
        <div class="mul-operation border-t w-full" v-if="isBatch === true">
          <div class="flex align-center" style="max-width: 1000px; margin: auto; flex-grow: 1">
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
              @click="openGenerateDialog()"
            >
              {{ $t('views.document.generateQuestion.title') }}
            </el-button>
            <el-button
              :disabled="multipleSelection.length === 0"
              @click="openSelectDocumentDialog()"
            >
              {{ $t('views.document.setting.migration') }}
            </el-button>

            <el-button :disabled="multipleSelection.length === 0" @click="deleteMulParagraph">
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
        </div>
      </LayoutContainer>
    </el-card>
    <ParagraphDialog
      ref="ParagraphDialogRef"
      :title="title"
      :apiType="apiType"
      @refresh="refresh"
    />
    <SelectDocumentDialog
      ref="SelectDocumentDialogRef"
      @refresh="refreshMigrateParagraph"
      :apiType="apiType"
      :workspaceId="knowledgeDetail.workspace_id"
    />
    <GenerateRelatedDialog ref="GenerateRelatedDialogRef" @refresh="refresh" :apiType="apiType" />
  </div>
</template>
<script setup lang="ts">
import { reactive, ref, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { CheckboxValueType } from 'element-plus'
import ParagraphDialog from './component/ParagraphDialog.vue'
import ParagraphCard from './component/ParagraphCard.vue'
import SelectDocumentDialog from './component/SelectDocumentDialog.vue'
import GenerateRelatedDialog from '@/components/generate-related-dialog/index.vue'
import { VueDraggable } from 'vue-draggable-plus'
import { MsgSuccess, MsgConfirm } from '@/utils/message'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import permissionMap from '@/permission'
import { t } from '@/locales'
import { cloneDeep } from 'lodash'
const route = useRoute()
const {
  params: { id, documentId },
  query: { from, isShared },
} = route as any

const apiType = computed<'systemShare' | 'workspace' | 'systemManage'>(() => {
  return from === 'systemShare' || from === 'systemManage' ? from : 'workspace'
})
const shareDisabled = computed(() => {
  return isShared === 'true'
})
const permissionPrecise = computed(() => {
  return permissionMap['knowledge'][apiType.value]
})

const SelectDocumentDialogRef = ref()
const ParagraphDialogRef = ref()
const loading = ref(false)
const changeStateloading = ref(false)
const documentDetail = ref<any>({})
const knowledgeDetail = ref<any>({})
const paragraphDetail = ref<any[]>([])
const title = ref('')
const search = ref('')
const searchType = ref('title')

const searchTypeChange = () => {
  search.value = ''
}

const dialogVisible = ref(false)
watch(
  () => ParagraphDialogRef.value?.dialogVisible,
  (val: boolean) => {
    dialogVisible.value = val
  },
)

function setPosition(val: string, index: number) {
  if (val === 'top') {
    return 1
  } else if (val === 'bottom') {
    return paragraphDetail.value[paragraphDetail.value.length - 1]?.position ?? paginationConfig.total
  } else if (val === 'up') {
    return paragraphDetail.value[index - 1]?.position ?? paragraphDetail.value[index].position
  } else if (val === 'down') {
    return paragraphDetail.value[index + 1]?.position ?? paragraphDetail.value[index].position
  }
}
function setTargetIndex(val: string, index: number) {
  if (val === 'top') return 0
  if (val === 'bottom') return paragraphDetail.value.length - 1
  if (val === 'up') return index - 1
  if (val === 'down') return index + 1
  return index
}
function dialogVisibleChange(val: boolean) {
  dialogVisible.value = val
}

const handleClick = (e: MouseEvent, ele: any) => {
  e.preventDefault()
  document.querySelector(`${ele}`)?.scrollIntoView({ block: 'nearest' })
}

// 批量操作
const isBatch = ref(false)
const multipleSelection = ref<any[]>([])
const checkAll = ref(false)
const isIndeterminate = computed(() => {
  return (
    multipleSelection.value.length > 0 &&
    multipleSelection.value.length < paragraphDetail.value.length
  )
})
const handleCheckAllChange = (val: CheckboxValueType) => {
  let bool
  if(isIndeterminate.value) {
    bool = true
  } else {
    bool = val as boolean
  }
  multipleSelection.value = bool ? paragraphDetail.value.map((v) => v.id) : []
  checkAll.value = bool as boolean
}

function toggleSelect(id: number) {
  const index = multipleSelection.value.indexOf(id)
  if (index === -1) {
    multipleSelection.value.push(id)
  } else {
    multipleSelection.value.splice(index, 1)
  }
}

const paginationConfig = reactive({
  current_page: 1,
  page_size: 30,
  total: 0,
})

function deleteParagraph(id: string) {
  const index = paragraphDetail.value.findIndex((v) => v.id === id)
  paragraphDetail.value.splice(index, 1)
}

function changeState(id: string, active: boolean) {
  const paragraph = paragraphDetail.value.find((item) => item.id === id)
  if (paragraph) paragraph.is_active = active
}

function refreshMigrateParagraph(data: any) {
  if (data) {
    multipleSelection.value = [data.id]
  }
  paragraphDetail.value = paragraphDetail.value.filter(
    (v) => !multipleSelection.value.includes(v.id),
  )
  multipleSelection.value = []
  MsgSuccess(t('views.document.tip.migrationSuccess'))
}

function openSelectDocumentDialog(row?: any) {
  if (row) {
    multipleSelection.value = [row.id]
  }
  SelectDocumentDialogRef.value.open(multipleSelection.value)
}
function deleteMulParagraph() {
  MsgConfirm(
    `${t('views.document.delete.confirmTitle1')} ${multipleSelection.value.length} ${t('views.document.delete.confirmTitle2')}`,
    t('views.paragraph.delete.confirmMessage'),
    {
      confirmButtonText: t('common.confirm'),
      confirmButtonClass: 'danger',
    },
  )
    .then(() => {
      loadSharedApi({ type: 'paragraph', systemType: apiType.value })
        .putMulParagraph(id, documentId, multipleSelection.value, changeStateloading)
        .then(() => {
          paragraphDetail.value = paragraphDetail.value.filter(
            (v) => !multipleSelection.value.includes(v.id),
          )
          multipleSelection.value = []
          MsgSuccess(t('views.document.delete.successMessage'))
        })
    })
    .catch(() => {})
}

function batchSelectedHandle(bool: boolean) {
  isBatch.value = bool
  checkAll.value = false
  multipleSelection.value = []
}

function searchHandle() {
  paginationConfig.current_page = 1
  paragraphDetail.value = []
  getParagraphList()
}

function addParagraph() {
  title.value = t('views.paragraph.addParagraph')
  ParagraphDialogRef.value.open()
}

function getDetail() {
  loadSharedApi({ type: 'document', isShared: shareDisabled.value, systemType: apiType.value })
    .getDocumentDetail(id, documentId, loading)
    .then((res: any) => {
      documentDetail.value = res.data
    })

  loadSharedApi({ type: 'knowledge', isShared: shareDisabled.value, systemType: apiType.value })
    .getKnowledgeDetail(id, loading)
    .then((res: any) => {
      knowledgeDetail.value = res.data
    })
}

function getParagraphList() {
  loadSharedApi({ type: 'paragraph', isShared: shareDisabled.value, systemType: apiType.value })
    .getParagraphPage(
      id,
      documentId,
      paginationConfig,
      search.value && { [searchType.value]: search.value },
      loading,
    )
    .then((res: any) => {
      paragraphDetail.value = [...paragraphDetail.value, ...res.data.records]
      paginationConfig.total = res.data.total
    })
}

function refresh(data: any) {
  if (data) {
    const index = paragraphDetail.value.findIndex((v) => v.id === data.id)
    paragraphDetail.value.splice(index, 1, data)
  } else {
    paginationConfig.current_page = 1
    paragraphDetail.value = []
    getParagraphList()
  }
}

const GenerateRelatedDialogRef = ref()
function openGenerateDialog(row?: any) {
  const arr: string[] = []
  if (row) {
    arr.push(row.id)
  } else {
    multipleSelection.value.map((v) => {
      if (v) {
        arr.push(v)
      }
    })
  }

  GenerateRelatedDialogRef.value.open(arr, 'paragraph')
}

function onEnd(event?: any, params?: any, index?: number) {
  console.log('onEnd', event, params, index)
  if (event && event.newIndex === event.oldIndex) {
    // 没有移动
    return
  }
  const p = cloneDeep(params)
  const obj = p ?? {
    paragraph_id: paragraphDetail.value[event.newIndex].id, // 当前拖动的段落ID
    // 向下拖动时取前一个元素的position，向上拖动时取后一个元素的position
    new_position:
      event.newIndex > event.oldIndex
        ? paragraphDetail.value[event.newIndex - 1]?.position ?? paragraphDetail.value.length
        : paragraphDetail.value[event.newIndex + 1]?.position ?? paragraphDetail.value.length,
  }
  // console.log(paragraphDetail.value[event.newIndex], obj)
  loadSharedApi({ type: 'paragraph', systemType: apiType.value }).putAdjustPosition(
    id,
    documentId,
    obj,
    loading,
  )
  if (params) {
    const movedItem = paragraphDetail.value.splice(index as number, 1)[0]
    paragraphDetail.value.splice(params.target_index, 0, movedItem)
  }
}

onMounted(() => {
  getDetail()
  getParagraphList()
})
</script>
<style lang="scss" scoped>
.paragraph {
  height: 100%;
  overflow: auto;
  min-width: 0;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 16px clamp(14px, 2.4vw, 32px);
  gap: 14px;
}
.paragraph-heading, .document-title, .header-button, .paragraph-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}
.paragraph-heading, .paragraph-filter {
  justify-content: space-between;
  flex-wrap: wrap;
}
.document-title { min-width: 0; flex: 1; }
.document-title h2 { font-size: 20px; line-height: 1.35; overflow-wrap: anywhere; color: var(--studio-ink); }
.header-button { flex-wrap: wrap; .el-button { margin: 0; } }
.paragraph-filter {
  border-bottom: 1px solid var(--studio-hairline);
  padding: 12px clamp(12px, 2vw, 20px);
  font-variant-numeric: tabular-nums;
  color: var(--app-text-color-secondary);
  .input-with-select { width: min(260px, 100%); }
}
.paragraph__main {
  --el-card-padding: 0;
  flex: 1;
  min-height: 250px;
  border: 1px solid var(--studio-hairline);
  border-radius: var(--app-border-radius-large);
  box-shadow: var(--studio-shadow);
  :deep(> .el-card__body), :deep(.layout-container__right) {
    min-height: 0;
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  :deep(.layout-container) { flex: 1; height: auto; min-height: 0; }
  .paragraph-sidebar, .paragraph-reader { width: 100%; height: 100%; box-sizing: border-box; min-height: 0; }
  .paragraph-reader { flex: 1; }
  :deep(.el-anchor) { background: transparent; }
  :deep(.el-anchor__link.is-active) { color: var(--studio-ink); font-weight: 600; }
  .mul-operation {
    position: static; margin: 0; width: 100%; padding: 10px 12px;
    > div { flex-wrap: wrap; gap: 8px; > * { margin: 0; } }
  }
}
.paragraph-detail {
  max-width: 1000px;
  margin: 0 auto;
  padding: 16px;
  box-sizing: border-box;
  .el-checkbox-group { font-size: inherit; line-height: inherit; }
  .paragraph-card { min-width: 0; align-items: flex-start; }
  .is-selected { border-color: var(--studio-ink); background: var(--studio-selection); }
  .handle-img { cursor: grab; }
}
@media (max-width: 760px) {
  .paragraph { padding-block: 12px; }
  .document-title { flex-basis: 100%; }
  .paragraph__main .paragraph-sidebar { max-height: 22dvh; }
  .paragraph-detail { padding: 10px; }
}
</style>
