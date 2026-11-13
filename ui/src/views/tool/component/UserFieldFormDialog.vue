<template>
  <el-dialog
    class="tool-editor-dialog tool-init-dialog"
    width="580px"
    align-center
    :title="isEdit ? $t('common.param.editParam') : $t('common.param.addParam')"
    v-model="dialogVisible"
    :close-on-click-modal="false"
    :destroy-on-close="true"
    :before-close="close"
    append-to-body
  >
    <DynamicsFormConstructor
      :model-value="currentRow"
      label-position="top"
      require-asterisk-position="right"
      :input_type_list="inputTypeList"
      ref="DynamicsFormConstructorRef"
    ></DynamicsFormConstructor>
    <p class="tool-form-error" role="alert" v-if="duplicate">
      {{ $t('workflow.nodes.variableAggregationNode.group.dupError') }}
    </p>
    <template #footer>
      <span class="tool-editor-actions">
        <el-button @click.prevent="close"> {{ $t('common.cancel') }} </el-button>
        <el-button type="primary" @click="submit()" :loading="loading">
          {{ isEdit ? $t('common.save') : $t('common.add') }}
        </el-button>
      </span>
    </template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { cloneDeep, get } from 'lodash'
import DynamicsFormConstructor from '@/components/dynamics-form/constructor/index.vue'
import '../tool-form.scss'
import { t } from '@/locales'
const emit = defineEmits(['refresh'])

const DynamicsFormConstructorRef = ref()
const loading = ref(false)
const duplicate = ref(false)
const usedNames = ref<string[]>([])
const isEdit = ref(false)
const currentItem = ref<Record<string, any>>()
const check_field = (field_list: Array<string>, obj: any) => {
  return field_list.every((field) => get(obj, field, undefined) !== undefined)
}
const currentRow = computed(() => {
  if (currentItem.value) {
    const row = currentItem.value
    switch (row.type) {
      case 'input':
        if (check_field(['field', 'input_type', 'label', 'required', 'attrs'], currentItem.value)) {
          return currentItem.value
        }
        return {
          attrs: row.attrs || { maxlength: 200, minlength: 0 },
          field: row.field || row.variable,
          input_type: 'TextInput',
          label: row.label || row.name,
          default_value: row.default_value,
          required: row.required != undefined ? row.required : row.is_required,
        }
      case 'select':
        if (
          check_field(
            ['field', 'input_type', 'label', 'required', 'option_list'],
            currentItem.value,
          )
        ) {
          return currentItem.value
        }
        return {
          attrs: row.attrs || {},
          field: row.field || row.variable,
          input_type: 'SingleSelect',
          label: row.label || row.name,
          default_value: row.default_value,
          required: row.required != undefined ? row.required : row.is_required,
          option_list: row.option_list
            ? row.option_list
            : (row.optionList ?? []).map((o: any) => {
                return { key: o, value: o }
              }),
        }

      case 'date':
        if (
          check_field(
            [
              'field',
              'input_type',
              'label',
              'required',
              'attrs.format',
              'attrs.value-format',
              'attrs.type',
            ],
            currentItem.value,
          )
        ) {
          return currentItem.value
        }
        return {
          field: row.field || row.variable,
          input_type: 'DatePicker',
          label: row.label || row.name,
          default_value: row.default_value,
          required: row.required != undefined ? row.required : row.is_required,
          attrs: {
            format: 'YYYY-MM-DD HH:mm:ss',
            'value-format': 'YYYY-MM-DD HH:mm:ss',
            type: 'datetime',
          },
        }
      default:
        return currentItem.value
    }
  } else {
    return {
      input_type: 'TextInput',
      required: false,
      attrs: { maxlength: 200, minlength: 0 },
      show_default_value: true,
    }
  }
})
const currentIndex = ref<number>()
const inputTypeList = ref([
  { label: t('dynamicsForm.input_type_list.TextInput'), value: 'TextInputConstructor' },
  { label: t('dynamicsForm.input_type_list.Slider'), value: 'SliderConstructor' },
  { label: t('dynamicsForm.input_type_list.PasswordInput'), value: 'PasswordInputConstructor' },
  { label: t('dynamicsForm.input_type_list.SingleSelect'), value: 'SingleSelectConstructor' },
  { label: t('dynamicsForm.input_type_list.MultiSelect'), value: 'MultiSelectConstructor' },
  { label: t('dynamicsForm.input_type_list.RadioCard'), value: 'RadioCardConstructor' },
  { label: t('dynamicsForm.input_type_list.DatePicker'), value: 'DatePickerConstructor' },
  { label: t('dynamicsForm.input_type_list.SwitchInput'), value: 'SwitchInputConstructor' },
  { label: t('dynamicsForm.input_type_list.JsonInput'), value: 'JsonInputConstructor' },
])

const dialogVisible = ref<boolean>(false)

const open = (row?: any, index?: number, names: string[] = []) => {
  usedNames.value = names
  duplicate.value = false
  isEdit.value = !!row
  dialogVisible.value = true

  currentItem.value = row ? cloneDeep(row) : undefined
  currentIndex.value = index
}

const close = () => {
  dialogVisible.value = false
  isEdit.value = false
  currentIndex.value = undefined
  currentItem.value = undefined
}

const submit = async () => {
  const formEl = DynamicsFormConstructorRef.value
  if (!formEl || loading.value) return
  loading.value = true
  try {
    if (
      !(await formEl.validate().then(
        () => true,
        () => false,
      ))
    )
      return
    const field = formEl.getData()
    field.field = field.field?.trim()
    duplicate.value = usedNames.value.includes(field.field)
    if (duplicate.value) return
    emit('refresh', field, currentIndex.value)
    close()
  } finally {
    loading.value = false
  }
}

defineExpose({ open, close })
</script>
