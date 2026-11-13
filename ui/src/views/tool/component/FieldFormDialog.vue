<template>
  <el-dialog
    class="tool-editor-dialog tool-field-dialog"
    width="520px"
    align-center
    :title="isEdit ? $t('common.param.editParam') : $t('common.param.addParam')"
    v-model="dialogVisible"
    :close-on-click-modal="false"
    destroy-on-close
    append-to-body
  >
    <el-form
      label-position="top"
      ref="fieldFormRef"
      :model="form"
      require-asterisk-position="right"
      class="tool-field-grid"
      @submit.prevent="submit"
    >
      <el-form-item
        class="tool-field-wide"
        :label="$t('views.tool.form.paramName.label')"
        prop="name"
        :rules="[
          {
            required: true,
            whitespace: true,
            message: $t('views.tool.form.paramName.requiredMessage'),
          },
          { validator: validateName },
        ]"
      >
        <el-input
          v-model="form.name"
          :placeholder="$t('views.tool.form.paramName.placeholder')"
          maxlength="64"
          show-word-limit
          @blur="form.name = form.name.trim()"
        />
      </el-form-item>
      <el-form-item :label="$t('views.tool.form.dataType.label')">
        <el-select v-model="form.type">
          <el-option v-for="item in typeOptions" :key="item" :label="item" :value="item" />
        </el-select>
      </el-form-item>
      <el-form-item :label="$t('views.tool.form.source.label')">
        <el-select v-model="form.source">
          <el-option :label="$t('views.tool.form.source.reference')" value="reference" />
          <el-option :label="$t('common.custom')" value="custom" />
        </el-select>
      </el-form-item>
      <el-form-item class="tool-field-wide" :label="$t('dynamicsForm.paramForm.tooltip.label')">
        <el-input
          v-model="form.desc"
          :placeholder="$t('dynamicsForm.paramForm.tooltip.placeholder')"
          maxlength="128"
          show-word-limit
          @blur="form.desc = form.desc?.trim()"
        />
      </el-form-item>
      <label class="tool-required-row tool-field-wide">
        {{ $t('dynamicsForm.paramForm.required.label') }}
        <el-switch
          v-model="form.is_required"
          :aria-label="$t('dynamicsForm.paramForm.required.label')"
        />
      </label>
      <button class="tool-submit-key" type="submit" tabindex="-1" aria-hidden="true"></button>
    </el-form>
    <template #footer>
      <div class="tool-editor-actions">
        <el-button @click="dialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="submit">{{
          $t(isEdit ? 'common.save' : 'common.add')
        }}</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { FormInstance } from 'element-plus'
import { cloneDeep } from 'lodash'
import { t } from '@/locales'
import '../tool-form.scss'

const typeOptions = ['string', 'int', 'dict', 'array', 'float', 'boolean']
const emit = defineEmits(['refresh'])
const fieldFormRef = ref<FormInstance>()
const dialogVisible = ref(false)
const isEdit = ref(false)
const usedNames = ref<string[]>([])
const newField = () => ({
  name: '',
  type: 'string',
  desc: '',
  source: 'reference',
  is_required: true,
})
const form = ref(newField())

function open(row?: Record<string, any>, names: string[] = []) {
  isEdit.value = !!row
  usedNames.value = names
  form.value = { ...newField(), ...cloneDeep(row) }
  dialogVisible.value = true
}
function validateName(_rule: unknown, value: string, done: (error?: Error) => void) {
  done(
    usedNames.value.includes(value?.trim())
      ? new Error(t('workflow.nodes.variableAggregationNode.group.dupError'))
      : undefined,
  )
}
async function submit() {
  form.value.name = form.value.name.trim()
  if (!(await fieldFormRef.value?.validate().catch(() => false)) || !dialogVisible.value) return
  emit('refresh', form.value)
  dialogVisible.value = false
}
defineExpose({ open })
</script>
