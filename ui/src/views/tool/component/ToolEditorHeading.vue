<template>
  <div class="tool-editor-heading">
    <button
      v-if="editable"
      type="button"
      class="tool-editor-mark is-editable"
      :title="$t('views.tool.editor.editIcon')"
      :aria-label="$t('views.tool.editor.editIcon')"
      @click="$emit('editIcon')"
    >
      <img :src="image" alt="" />
      <AppIcon iconName="app-edit" />
    </button>
    <span v-else class="tool-editor-mark" aria-hidden="true"><img :src="image" alt="" /></span>
    <h2 :id="titleId">{{ title }}</h2>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { isAppIcon } from '@/utils/common'
import '../tool-form.scss'

const props = defineProps<{
  title?: string
  titleId?: string
  icon?: string
  fallback: string
  editable?: boolean
}>()
defineEmits<{ editIcon: [] }>()
const image = computed(() => (isAppIcon(props.icon) ? props.icon : props.fallback))
</script>
