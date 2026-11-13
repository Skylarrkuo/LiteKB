<template>
  <div class="hit-test">
    <header class="hit-heading">
      <h2>{{ $t('views.application.hitTest.title') }}</h2>
      <p>{{ $t('views.application.hitTest.text') }}</p>
    </header>
    <div class="hit-test__operate" v-if="!route.path.includes('share/')">
      <el-popover
        :visible="popoverVisible"
        placement="bottom-end"
        popper-class="knowledge-retrieval-settings"
        :width="'min(500px, calc(100vw - 28px))'"
        :popper-style="{ maxHeight: 'min(68dvh, 620px)', overflowY: 'auto' }"
        trigger="click"
        :persistent="false"
      >
        <template #reference>
          <el-button
            class="settings-button"
            :aria-expanded="popoverVisible"
            @click="settingChange('open')"
          >
            <AppIcon iconName="app-setting"></AppIcon>
            {{ $t('common.paramSetting') }}</el-button
          >
        </template>
        <div class="mb-16">
          <div class="title mb-8">
            {{ $t('views.application.dialog.selectSearchMode') }}
          </div>
          <el-radio-group
            v-model="cloneForm.search_mode"
            class="card__radio"
            @change="changeHandle"
          >
            <el-card
              shadow="never"
              class="mb-16"
              :class="cloneForm.search_mode === 'embedding' ? 'border-active' : ''"
            >
              <el-radio value="embedding" size="large">
                <p class="mb-4">
                  {{ $t('views.application.dialog.vectorSearch') }}
                </p>
                <el-text type="info">{{
                  $t('views.application.dialog.vectorSearchTooltip')
                }}</el-text>
              </el-radio>
            </el-card>
            <el-card
              shadow="never"
              class="mb-16"
              :class="cloneForm.search_mode === 'keywords' ? 'border-active' : ''"
            >
              <el-radio value="keywords" size="large">
                <p class="mb-4">
                  {{ $t('views.application.dialog.fullTextSearch') }}
                </p>
                <el-text type="info">{{
                  $t('views.application.dialog.fullTextSearchTooltip')
                }}</el-text>
              </el-radio>
            </el-card>
            <el-card
              shadow="never"
              class="mb-16"
              :class="cloneForm.search_mode === 'blend' ? 'border-active' : ''"
            >
              <el-radio value="blend" size="large">
                <p class="mb-4">
                  {{ $t('views.application.dialog.hybridSearch') }}
                </p>
                <el-text type="info">{{
                  $t('views.application.dialog.hybridSearchTooltip')
                }}</el-text>
              </el-radio>
            </el-card>
            <el-card shadow="never" class="mb-16" :class="{ 'border-active': cloneForm.search_mode === 'rrf' }">
              <el-radio value="rrf" size="large">
                <p class="mb-4">{{ $t('views.application.dialog.rankFusion') }}</p>
                <el-text type="info">{{ $t('views.application.dialog.rankFusionTooltip') }}</el-text>
              </el-radio>
            </el-card>
          </el-radio-group>
        </div>
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="mb-16">
              <div class="title mb-8">
                {{ $t('views.application.dialog.similarityThreshold') }}
              </div>
              <el-input-number
                v-model="cloneForm.similarity"
                :min="0"
                :max="['blend', 'rrf'].includes(cloneForm.search_mode) ? 2 : 1"
                :precision="3"
                :step="0.1"
                :value-on-clear="0"
                controls-position="right"
                class="w-full"
              />
            </div>
          </el-col>
          <el-col :span="12">
            <div class="mb-16">
              <div class="title mb-8">
                {{ $t('views.application.dialog.topReferences') }}
              </div>
              <el-input-number
                v-model="cloneForm.top_number"
                :min="1"
                :max="10000"
                controls-position="right"
                class="w-full"
              />
            </div>
          </el-col>
        </el-row>

        <div class="text-right">
          <el-button @click="popoverVisible = false">{{ $t('common.cancel') }}</el-button>
          <el-button type="primary" @click="settingChange('close')">{{
            $t('common.confirm')
          }}</el-button>
        </div>
      </el-popover>
      <div class="query-input">
        <el-icon aria-hidden="true"><Search /></el-icon>
        <el-input
          ref="quickInputRef"
          v-model="inputValue"
          type="textarea"
          :aria-label="$t('common.search')"
          :placeholder="$t('common.inputPlaceholder')"
          :autosize="{ minRows: 1, maxRows: 4 }"
          @keydown.enter="sendChatHandle"
        />
        <el-button type="primary" :disabled="isDisabledChart || loading" @click="getHitTestList()">
          {{ $t('common.search') }}
        </el-button>
      </div>
    </div>
    <section class="hit-results" v-loading="loading" :aria-label="$t('views.application.hitTest.title')">
      <div v-if="questionTitle" class="tested-query">
        <el-icon aria-hidden="true"><Search /></el-icon>
        <h3>{{ questionTitle }}</h3>
      </div>
      <el-empty v-if="!paragraphDetail.length" class="hit-empty"
        :description="$t(first ? 'views.application.hitTest.emptyMessage1' : 'views.application.hitTest.emptyMessage2')">
        <template #image><el-icon aria-hidden="true"><Document /></el-icon></template>
      </el-empty>
      <div v-else class="hit-grid">
        <CardBox
          v-for="(item, index) in paragraphDetail"
          :key="item.id"
          shadow="hover"
          :title="item.title || '-'"
          :description="item.content"
          class="document-card cursor"
          :class="item.is_active ? '' : 'disabled'"
          @click="editParagraph(item)"
        >
          <template #icon>
            <el-avatar class="rank-number" :size="22"> {{ index + 1 + '' }}</el-avatar>
          </template>
          <template #tag>
            <span class="score" :title="$t('views.application.dialog.similarityTooltip')">{{ item.similarity?.toFixed(3) }}</span>
          </template>
          <template #footer>
            <div class="footer-content flex-between">
              <el-text truncated :title="item?.document_name">
                <el-icon>
                  <Document />
                </el-icon>
                {{ item?.document_name }}
              </el-text>
              <div v-if="item.trample_num || item.star_num">
                <span v-if="item.star_num">
                  <AppIcon iconName="app-like-color"></AppIcon>
                  {{ item.star_num }}
                </span>
                <span v-if="item.trample_num" class="ml-4">
                  <AppIcon iconName="app-oppose-color"></AppIcon>
                  {{ item.trample_num }}
                </span>
              </div>
            </div>
          </template>
        </CardBox>
      </div>
    </section>
    <ParagraphDialog
      ref="ParagraphDialogRef"
      :title="title"
      @refresh="refresh"
      :apiType="apiType"
    />

  </div>
</template>
<script setup lang="ts">
import { nextTick, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { cloneDeep } from 'lodash'
import ParagraphDialog from '@/views/paragraph/component/ParagraphDialog.vue'
import { t } from '@/locales'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
const route = useRoute()
const {
  params: { id },
} = route as any
const apiType = computed(() => {
  if (route.path.includes('shared')) {
    return 'systemShare'
  } else if (route.path.includes('resource-management')) {
    return 'systemManage'
  } else {
    return 'workspace'
  }
})
const quickInputRef = ref()
const ParagraphDialogRef = ref()
const loading = ref(false)
const paragraphDetail = ref<any[]>([])
const title = ref('')
const inputValue = ref('')
const formInline = ref({
  similarity: 0.6,
  top_number: 5,
  search_mode: 'embedding',
})

// 第一次加载
const first = ref(true)

const cloneForm = ref<any>({})

const popoverVisible = ref(false)
const questionTitle = ref('')

const isDisabledChart = computed(() => !inputValue.value.trim())

function changeHandle(val: string) {
  if (val === 'keywords' || val === 'rrf') {
    cloneForm.value.similarity = 0
  } else {
    cloneForm.value.similarity = 0.6
  }
}

function settingChange(val: string) {
  if (val === 'open') {
    popoverVisible.value = true
    cloneForm.value = cloneDeep(formInline.value)
  } else if (val === 'close') {
    popoverVisible.value = false
    formInline.value = cloneDeep(cloneForm.value)
  }
}

function editParagraph(row: any) {
  title.value = t('views.paragraph.paragraphDetail')
  ParagraphDialogRef.value.open(row)
}

function sendChatHandle(event: KeyboardEvent) {
  if (event.isComposing || event.keyCode === 229) return
  if (!event?.ctrlKey && !event?.shiftKey && !event?.altKey && !event?.metaKey) {
    // 如果没有按下组合键，则会阻止默认事件
    event.preventDefault()
    if (!isDisabledChart.value && !loading.value) {
      getHitTestList()
    }
  } else {
    // 如果同时按下ctrl/shift/cmd/opt +enter，则会换行
    insertNewlineAtCursor(event)
  }
}
const insertNewlineAtCursor = (event?: any) => {
  const textarea = quickInputRef.value.$el.querySelector(
    '.el-textarea__inner',
  ) as HTMLTextAreaElement
  const startPos = textarea.selectionStart
  const endPos = textarea.selectionEnd
  // 阻止默认行为（避免额外的换行符）
  event.preventDefault()
  // 在光标处插入换行符
  inputValue.value = inputValue.value.slice(0, startPos) + '\n' + inputValue.value.slice(endPos)
  nextTick(() => {
    textarea.setSelectionRange(startPos + 1, startPos + 1) // 光标定位到换行后位置
  })
}

function getHitTestList(query = inputValue.value.trim()) {
  if (!query || loading.value) return
  const obj = {
    query_text: query,
    ...formInline.value,
  }
  loadSharedApi({ type: 'knowledge', systemType: apiType.value })
    .putKnowledgeHitTest(id, obj, loading)
    .then((res: any) => {
      paragraphDetail.value = res.data
      questionTitle.value = query
      first.value = false
    })
}

function refresh(data: any) {
  if (data) {
    const obj = paragraphDetail.value.filter((v) => v.id === data.id)[0]
    obj.content = data.content
    obj.title = data.title
  } else {
    getHitTestList(questionTitle.value)
  }
}

</script>
<style lang="scss" scoped>
:global(.el-popover.el-popper.knowledge-retrieval-settings) {
  border-radius: var(--app-border-radius-large);
  border-color: var(--studio-hairline);
  box-shadow: var(--studio-shadow);
  padding: 16px;
}
.hit-test {
  height: 100%;
  min-width: 0;
  overflow: auto;
  box-sizing: border-box;
  padding: 20px clamp(14px, 2.4vw, 32px);
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.hit-heading {
  h2 { margin: 0; font-size: 22px; line-height: 1.3; color: var(--studio-ink); }
  p { margin: 5px 0 0; color: var(--app-text-color-secondary); line-height: 1.5; }
}
.hit-test__operate {
  display: flex;
  flex-wrap: wrap-reverse;
  align-items: center;
  gap: 10px;
  .settings-button { order: 1; }
}
.query-input {
  display: flex;
  align-items: center;
  flex: 1 1 320px;
  min-width: 0;
  gap: 8px;
  padding: 6px 8px 6px 14px;
  border: 1px solid var(--studio-hairline);
  border-radius: var(--app-border-radius-base);
  background: var(--app-view-bg-color);
  > .el-icon { color: var(--studio-ink); }
  &:focus-within { border-color: var(--studio-ink); }
  :deep(.el-textarea__inner) { box-shadow: none; resize: none; padding: 5px 0; }
}
.hit-results {
  flex: 1 0 auto;
  min-height: 230px;
  padding: clamp(12px, 1.6vw, 22px);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  border: 1px solid var(--studio-hairline);
  border-radius: var(--app-border-radius-large);
  background: var(--app-view-bg-color);
  box-shadow: var(--studio-shadow);
}
.tested-query { display: flex; align-items: baseline; gap: 8px; color: var(--studio-ink); margin-bottom: 16px; }
.tested-query h3 { font-size: 16px; line-height: 1.5; overflow-wrap: anywhere; }
.hit-empty {
  flex: 1;
  :deep(.el-empty__image) {
    width: 54px; height: 54px; display: grid; place-items: center;
    border-radius: var(--app-border-radius-large); background: var(--studio-selection); color: var(--studio-ink);
    .el-icon { font-size: 26px; }
  }
}
.hit-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 280px), 1fr)); gap: 12px; }
.document-card {
  --card-min-width: 0;
  --app-card-box-description-height: auto;
  min-height: 176px;
  border-color: var(--studio-hairline);
  border-radius: var(--app-border-radius-base);
  box-shadow: none;
  &:hover, &:focus-visible { border-color: var(--studio-ink); }
  .rank-number { color: var(--studio-ink); background: var(--studio-selection); font-variant-numeric: tabular-nums; }
  .score { font-variant-numeric: tabular-nums; color: var(--studio-ink); font-size: 12px; font-weight: 650; }
  :deep(.title) { padding-right: 42px; }
  :deep(.description .content) { -webkit-line-clamp: 3; }
  :deep(.card-footer > div), .footer-content { min-width: 0; }
  &.disabled { background: var(--app-layout-bg-color); }
}
@media (max-width: 760px) {
  .hit-test { padding-block: 14px; gap: 12px; }
  .hit-test__operate { flex-direction: column; align-items: stretch; }
  .query-input { flex-basis: auto; }
  .settings-button { align-self: flex-start; }
}
</style>
