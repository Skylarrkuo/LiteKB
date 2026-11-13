<template>
  <el-dialog
    v-model="dialogVisible"
    class="provider-dialog"
    width="660px"
    :title="$t('views.model.providerPlaceholder')"
    :close-on-click-modal="false"
    destroy-on-close
    append-to-body
  >
    <template #header="{ titleId }">
      <h2 :id="titleId" class="picker-title">{{ $t('views.model.providerPlaceholder') }}</h2>
    </template>
    <div class="picker-filters">
      <el-input
        v-model="query"
        clearable
        :placeholder="$t('studio.findProvider')"
        :aria-label="$t('studio.findProvider')"
      >
        <template #prefix
          ><el-icon><Search /></el-icon
        ></template>
      </el-input>
      <el-select
        v-model="selectModelType"
        :empty-values="[null, undefined]"
        :placeholder="$t('views.model.modelType.allModel')"
        :aria-label="$t('views.model.modelForm.model_type.label')"
        @change="checkModelType"
      >
        <el-option
          v-for="item in modelTypeOptions"
          :key="item.value"
          :value="item.value"
          :label="item.text"
        />
      </el-select>
    </div>
    <div class="picker-options" v-loading="loading" :aria-busy="loading">
      <div v-if="visibleProviders.length" class="provider-grid">
        <button
          v-for="provider in visibleProviders"
          :key="provider.provider"
          type="button"
          class="provider-choice"
          @click="goCreate(provider)"
        >
          <span class="provider-mark" aria-hidden="true">
            <span v-if="provider.icon" :innerHTML="provider.icon" />
            <el-icon v-else><Connection /></el-icon>
          </span>
          <span class="provider-name">{{ provider.name }}</span>
          <el-icon class="choice-arrow" aria-hidden="true"><ArrowRight /></el-icon>
        </button>
      </div>
      <p v-else-if="!loading" class="picker-empty">{{ $t('common.noData') }}</p>
    </div>
  </el-dialog>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import ProviderApi from '@/api/model/provider'
import type { Provider } from '@/api/type/model'
import { modelTypeList } from './data'
import { mediaModelsEnabled } from '@/workflow/capabilities'
import { t } from '@/locales'

const loading = ref(false)
const dialogVisible = ref(false)
const providers = ref<Provider[]>([])
const query = ref('')
const selectModelType = ref('')
const modelTypeOptions = computed(() => [
  { text: t('views.model.modelType.allModel'), value: '' },
  ...modelTypeList.filter(
    (type) => mediaModelsEnabled.value || !['STT', 'TTS', 'TTI', 'TTV', 'ITV'].includes(type.value),
  ),
])
const visibleProviders = computed(() => {
  const search = query.value.trim().toLocaleLowerCase()
  return providers.value.filter((item) =>
    (item.name + ' ' + item.provider).toLocaleLowerCase().includes(search),
  )
})
let generation = 0

function open(modelType?: string) {
  dialogVisible.value = true
  query.value = ''
  selectModelType.value = modelType ?? selectModelType.value
  checkModelType(selectModelType.value)
}
function close() {
  dialogVisible.value = false
}
async function checkModelType(modelType: string) {
  const request = ++generation
  providers.value = []
  loading.value = true
  try {
    const { data } = await ProviderApi.getProviderByModelType(modelType)
    if (request === generation)
      providers.value = [...data].sort((a, b) => a.name.localeCompare(b.name))
  } finally {
    if (request === generation) loading.value = false
  }
}

const emit = defineEmits<{ change: [provider: Provider, modelType: string] }>()
function goCreate(provider: Provider) {
  close()
  emit('change', provider, selectModelType.value)
}
defineExpose({ open, close })
</script>
<style scoped>
.picker-title {
  font-size: 23px;
  font-weight: 650;
  letter-spacing: -0.035em;
  margin: 2px 32px 0 0;
}
.picker-filters {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(125px, 38%);
  gap: 10px;
  margin: 5px 0 18px;
}
.picker-options {
  min-height: 130px;
  max-height: min(55dvh, 440px);
  overflow-y: auto;
  padding: 3px;
}
.provider-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
}
.provider-choice {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 62px;
  text-align: left;
  padding: 10px 13px;
  border: 1px solid var(--studio-hairline);
  border-radius: 13px;
  background: white;
  color: var(--el-text-color-primary);
  font: inherit;
  font-weight: 550;
  cursor: pointer;
}
.provider-choice:hover,
.provider-choice:focus-visible {
  background: #f1f8f4;
  border-color: #a2c5b7;
}
.provider-mark {
  flex: 0 0 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: #f3f6f4;
}
.provider-mark > span,
.provider-mark :deep(svg),
.provider-mark :deep(img) {
  display: block;
  width: 24px;
  height: 24px;
  object-fit: contain;
}
.provider-name {
  min-width: 0;
  overflow-wrap: anywhere;
}
.choice-arrow {
  margin-left: auto;
  color: #678277;
  font-size: 12px;
}
.picker-empty {
  padding: 46px 12px;
  text-align: center;
  color: var(--app-text-color-secondary);
}
@media (max-width: 540px) {
  .provider-grid {
    grid-template-columns: 1fr;
  }
  .provider-choice {
    min-height: 50px;
  }
  .picker-filters {
    grid-template-columns: minmax(0, 1fr) minmax(0, 0.85fr);
  }
}
</style>
