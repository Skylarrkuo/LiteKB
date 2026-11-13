<template>
  <section class="tool-params">
    <div class="tool-section-heading">
      <div>
        <h3>{{ title }}</h3>
        <p v-if="hint">{{ hint }}</p>
      </div>
      <el-button
        v-if="rows?.length && editable"
        class="tool-param-add"
        @click="open()"
        :aria-label="title + ' · ' + $t('common.add')"
      >
        <AppIcon iconName="app-add-outlined" />{{ $t('common.add') }}
      </el-button>
    </div>
    <ul v-if="rows?.length" class="tool-param-list">
      <li v-for="(row, index) in rows" :key="index">
        <div class="tool-param-info">
          <code>{{ kind === 'init' ? row.field || row.variable : row.name }}</code>
          <small v-if="description(row)">{{ description(row) }}</small>
          <div class="tool-param-meta">
            <span>{{ typeLabel(row) }}</span>
            <span v-if="kind === 'input'">{{
              row.source === 'custom' ? $t('common.custom') : $t('views.tool.form.source.reference')
            }}</span>
            <span v-if="kind === 'init' && (row.required ?? row.is_required)">{{
              $t('common.required')
            }}</span>
          </div>
        </div>
        <div class="tool-param-actions">
          <label v-if="kind === 'input'" class="tool-param-required">
            {{ $t('common.required') }}
            <el-switch
              size="small"
              :model-value="row.is_required"
              :disabled="!editable"
              :aria-label="row.name + ' · ' + $t('common.required')"
              @change="setRequired(index, Boolean($event))"
            />
          </label>
          <template v-if="editable">
            <el-button
              text
              circle
              :title="$t('common.modify')"
              :aria-label="$t('common.modify') + ' ' + (row.field || row.name || '')"
              @click="open(index)"
            >
              <AppIcon iconName="app-edit" />
            </el-button>
            <el-button
              text
              circle
              :title="$t('common.delete')"
              :aria-label="$t('common.delete') + ' ' + (row.field || row.name || '')"
              @click="remove(index)"
            >
              <AppIcon iconName="app-delete" />
            </el-button>
          </template>
        </div>
      </li>
    </ul>
    <div v-else class="tool-param-empty">
      <span>{{
        $t(kind === 'init' ? 'views.tool.editor.emptyInit' : 'views.tool.editor.emptyInput')
      }}</span>
      <el-button
        v-if="editable"
        link
        type="primary"
        @click="open()"
        :aria-label="title + ' · ' + $t('common.add')"
      >
        <AppIcon iconName="app-add-outlined" />{{ $t('common.add') }}
      </el-button>
    </div>
  </section>
  <FieldFormDialog v-if="kind === 'input'" ref="inputEditor" @refresh="apply" />
  <UserFieldFormDialog v-else ref="initEditor" @refresh="apply" />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import FieldFormDialog from './FieldFormDialog.vue'
import UserFieldFormDialog from './UserFieldFormDialog.vue'
import { t } from '@/locales'
import { input_type_list } from '@/components/dynamics-form/constructor/data'

const props = defineProps<{
  rows?: Record<string, any>[]
  kind: 'init' | 'input'
  hint?: string
  editable: boolean
}>()
const emit = defineEmits<{ 'update:rows': [rows: Record<string, any>[]] }>()
const inputEditor = ref<InstanceType<typeof FieldFormDialog>>()
const initEditor = ref<InstanceType<typeof UserFieldFormDialog>>()
const editingIndex = ref<number>()
function open(index?: number) {
  editingIndex.value = index
  const rows = props.rows ?? []
  const row = index === undefined ? undefined : rows[index]
  const names = rows
    .filter((_, i) => i !== index)
    .map((item) => (props.kind === 'init' ? item.field || item.variable : item.name))
  if (props.kind === 'input') inputEditor.value?.open(row, names)
  else initEditor.value?.open(row, index, names)
}
function apply(row: Record<string, any>) {
  const rows = [...(props.rows ?? [])]
  if (editingIndex.value === undefined) rows.push(row)
  else rows[editingIndex.value] = row
  emit('update:rows', rows)
}
function remove(index: number) {
  emit(
    'update:rows',
    (props.rows ?? []).filter((_, i) => i !== index),
  )
}
function setRequired(index: number, required: boolean) {
  emit(
    'update:rows',
    (props.rows ?? []).map((row, i) => (i === index ? { ...row, is_required: required } : row)),
  )
}
const title = computed(() =>
  t(props.kind === 'init' ? 'common.param.initParam' : 'common.param.inputParam'),
)
function description(row: Record<string, any>) {
  return props.kind === 'input'
    ? row.desc
    : typeof row.label === 'string'
      ? row.label
      : row.label?.label
}
function typeLabel(row: Record<string, any>) {
  if (props.kind === 'input') return row.type
  return (
    input_type_list.find((item) => item.value === row.input_type)?.label ||
    row.input_type ||
    row.type
  )
}
</script>
