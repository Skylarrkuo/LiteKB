<template>
  <section class="brand-settings">
    <h2>{{ $t('studio.brand') }}</h2>
    <el-form label-position="top" @submit.prevent="save" v-loading="loading">
      <el-form-item :label="$t('studio.name')">
        <el-input v-model="draft.name" maxlength="60" show-word-limit />
      </el-form-item>
      <el-form-item :label="$t('studio.icon')">
        <div class="icon-controls">
          <img :src="draft.icon || defaultIcon" alt="" width="54" height="54" />
          <input ref="picker" type="file" accept="image/png" hidden @change="readIcon" />
          <el-button @click="picker?.click()">{{ $t('studio.chooseIcon') }}</el-button>
          <el-button v-if="draft.icon" link @click="draft.icon = ''">{{
            $t('studio.resetIcon')
          }}</el-button>
        </div>
        <small>PNG · ≤ 512 × 512 · ≤ 256 KiB</small>
      </el-form-item>
      <el-button native-type="submit" type="primary" :disabled="!draft.name.trim() || !dirty">{{
        $t('common.save')
      }}</el-button>
    </el-form>
  </section>
</template>
<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { branding, defaultIcon, loadBranding, saveBranding } from '@/utils/branding'
import { ElMessage } from 'element-plus'
import { t } from '@/locales'

const draft = reactive({ ...branding })
const picker = ref<HTMLInputElement>()
const loading = ref(false)
const dirty = computed(() => draft.name !== branding.name || draft.icon !== branding.icon)
onMounted(async () => {
  loading.value = true
  try {
    await loadBranding()
    Object.assign(draft, branding)
  } finally {
    loading.value = false
  }
})
async function readIcon(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (file.type !== 'image/png' || file.size > 256 * 1024)
    return ElMessage.error(t('studio.iconError'))
  try {
    const bitmap = await createImageBitmap(file)
    const valid = bitmap.width <= 512 && bitmap.height <= 512
    bitmap.close()
    if (!valid) return ElMessage.error(t('studio.iconError'))
    const reader = new FileReader()
    reader.onload = () => {
      draft.icon = String(reader.result)
    }
    reader.onerror = () => ElMessage.error(t('studio.iconError'))
    reader.readAsDataURL(file)
  } catch {
    ElMessage.error(t('studio.iconError'))
  }
}
async function save() {
  if (loading.value || !dirty.value || !draft.name.trim()) return
  loading.value = true
  try {
    await saveBranding({ name: draft.name.trim(), icon: draft.icon })
    Object.assign(draft, branding)
    ElMessage.success(t('studio.saved'))
  } finally {
    loading.value = false
  }
}
</script>
<style scoped>
.brand-settings {
  max-width: 560px;
  padding: clamp(16px, 2.5vw, 36px);
}
h2 {
  margin: 0 0 24px;
  font-size: 25px;
  font-weight: 650;
  letter-spacing: -0.04em;
}
.el-form {
  padding: clamp(16px, 2.2vw, 28px);
  background: white;
  border-radius: 16px;
  border: 1px solid var(--studio-hairline);
  box-shadow: var(--studio-shadow);
}
small {
  width: 100%;
  margin-top: 4px;
  color: var(--el-text-color-secondary);
}
.icon-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.icon-controls img {
  object-fit: contain;
}
</style>
