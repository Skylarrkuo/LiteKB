<template>
  <el-dialog
    class="tool-editor-dialog tool-config-dialog"
    :title="$t('views.tool.mcp.mcpConfig')"
    width="620px"
    align-center
    v-model="dialogVisible"
    append-to-body
  >
    <el-input
      class="tool-json"
      type="textarea"
      readonly
      :model-value="config"
      :aria-label="$t('views.tool.mcp.mcpConfig')"
      :autosize="{ minRows: 7, maxRows: 18 }"
      spellcheck="false"
    />
    <template #footer>
      <div class="tool-editor-actions">
        <el-button @click="dialogVisible = false">{{ $t('common.close') }}</el-button>
        <el-button type="primary" @click="copyClick(config)" :disabled="!config">
          <AppIcon iconName="app-copy" />{{ $t('common.copy') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { copyClick } from '@/utils/clipboard'
import '../tool-form.scss'

const config = ref('')
const dialogVisible = ref(false)
function open(item: { code: string }) {
  config.value = item.code
  dialogVisible.value = true
}
defineExpose({ open })
</script>
