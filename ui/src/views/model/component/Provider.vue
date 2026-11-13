<template>
  <div class="provider-list" v-loading="loading">
    <button
      v-if="showShared && hasPermission(EditionConst.IS_EE, 'OR')"
      type="button"
      class="provider-row"
      :aria-pressed="active?.provider === 'share'"
      @click="emit('click', { provider: 'share', name: $t('views.shared.shared_model'), icon: '' })"
    >
      <AppIcon iconName="app-shared-active" aria-hidden="true" />{{
        $t('views.shared.shared_model')
      }}
    </button>
    <button
      type="button"
      class="provider-row all-models"
      :aria-pressed="!active?.provider"
      @click="emit('click', allObj)"
    >
      <AppIcon iconName="app-all-menu-active" aria-hidden="true" />{{
        $t('views.model.modelType.allModel')
      }}
    </button>
    <details v-for="group in groups" :key="group.title" open>
      <summary>
        <el-icon class="provider-chevron" aria-hidden="true"><ArrowRight /></el-icon>
        {{ $t(group.title) }}
      </summary>
      <button
        v-for="item in group.items"
        :key="item.provider"
        type="button"
        class="provider-row"
        :aria-pressed="active?.provider === item.provider"
        :title="item.name"
        @click="emit('click', item)"
      >
        <span v-if="item.icon" class="provider-icon" :innerHTML="item.icon" aria-hidden="true" />
        <el-icon v-else aria-hidden="true"><Connection /></el-icon>
        <span class="provider-name">{{ item.name }}</span>
      </button>
    </details>
  </div>
</template>
<script lang="ts" setup>
import { computed } from 'vue'
import type { Provider } from '@/api/type/model'
import { allObj } from './data'
import { EditionConst } from '@/utils/permission/data'
import { hasPermission } from '@/utils/permission/index'

const props = defineProps<{
  data: Provider[]
  loading: boolean
  showShared?: boolean
  active?: Provider
}>()
const emit = defineEmits<{ click: [provider: Provider] }>()
const localProviders = new Set([
  'model_ollama_provider',
  'model_local_provider',
  'model_xinference_provider',
  'model_vllm_provider',
  'model_docker_ai_provider',
])
const groups = computed(() => {
  const items = props.data
    .filter((item) => item.provider)
    .sort((a, b) => a.name.localeCompare(b.name))
  return [
    {
      title: 'views.model.modelType.publicModel',
      items: items.filter((item) => !localProviders.has(item.provider)),
    },
    {
      title: 'views.model.modelType.privateModel',
      items: items.filter((item) => localProviders.has(item.provider)),
    },
  ].filter((group) => group.items.length)
})
</script>
<style scoped>
.provider-list {
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  height: 100%;
  box-sizing: border-box;
  padding: 0 10px 20px;
}
.provider-row,
summary {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  background: transparent;
  color: var(--el-text-color-regular);
  border: 0;
  cursor: pointer;
  text-align: left;
  font: inherit;
  border-radius: 8px;
}
.provider-row {
  min-height: 35px;
  padding: 6px 12px;
  margin-bottom: 2px;
}
.provider-row:hover,
summary:hover {
  background: #e3ebe5;
}
.provider-row[aria-pressed='true'] {
  color: var(--studio-ink);
  background: #d7ebe0;
  font-weight: 600;
}
.provider-row:focus-visible,
summary:focus-visible {
  outline-offset: -2px;
}
.provider-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.provider-icon,
.provider-icon :deep(svg),
.provider-icon :deep(img) {
  display: block;
  width: 19px;
  height: 19px;
  flex: 0 0 19px;
  object-fit: contain;
}
.all-models {
  flex-shrink: 0;
  margin: 0 0 8px;
  font-weight: 550;
}
details + details {
  margin-top: 10px;
}
summary {
  list-style: none;
  padding: 9px 6px;
  font-size: 12px;
  color: #556b60;
  font-weight: 650;
}
summary::-webkit-details-marker {
  display: none;
}
.provider-chevron {
  font-size: 11px;
}
details[open] > summary .provider-chevron {
  transform: rotate(90deg);
}
</style>
