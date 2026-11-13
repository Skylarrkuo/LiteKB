<template>
  <section class="overview" v-loading="loading">
    <h2>{{ $t('views.applicationOverview.title') }}</h2>
    <el-card shadow="never">
      <h3>{{ detail?.name }}</h3>
      <p v-if="detail?.desc">{{ detail.desc }}</p>
      <dl>
        <dt>Agent ID</dt>
        <dd>
          <code>{{ id }}</code>
        </dd>
        <dt>Run API</dt>
        <dd>
          <code>POST {{ origin }}/v1/agents/{{ id }}/runs</code>
        </dd>
        <dt>Chat API</dt>
        <dd>
          <code>{{ baseUrl }}/{{ id }}/chat/completions</code>
        </dd>
      </dl>
      <el-button
        v-if="permissionMap.application.workspace.overview_api_key(id)"
        @click="keys?.open()"
        >Chat API Key</el-button
      >
    </el-card>
    <APIKeyDialog ref="keys" />
  </section>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import permissionMap from '@/permission'
import { loadSharedApi } from '@/utils/dynamics-api/shared-api'
import APIKeyDialog from './component/APIKeyDialog.vue'

const id = String(useRoute().params.id)
const origin = window.location.origin
const baseUrl = origin + window.MaxKB.chatPrefix + '/api'
const loading = ref(false),
  detail = ref<{ name: string; desc: string }>()
const keys = ref<InstanceType<typeof APIKeyDialog>>()
onMounted(async () => {
  const response = await loadSharedApi({
    type: 'application',
    systemType: 'workspace',
  }).getApplicationDetail(id, loading)
  detail.value = response.data
})
</script>
<style scoped>
.overview {
  max-width: 920px;
  padding: 24px;
}
h2 {
  margin-bottom: 20px;
}
dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 12px;
  margin: 20px 0;
}
dt {
  color: var(--el-text-color-secondary);
}
dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
