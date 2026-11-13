<template>
  <nav class="settings-tabs" :aria-label="$t('common.setting')">
    <RouterLink v-if="hasPermission(model.meta.permission, 'OR')" to="/settings/models">{{
      $t('views.model.title')
    }}</RouterLink>
    <template v-if="hasPermission(RoleConst.ADMIN, 'OR')">
      <RouterLink to="/settings/branding">{{ $t('studio.brand') }}</RouterLink>
      <RouterLink to="/settings/accounts">{{ $t('views.userManage.title') }}</RouterLink>
    </template>
  </nav>
  <div class="settings-content"><RouterView /></div>
</template>
<script setup lang="ts">
import { RoleConst } from '@/utils/permission/data'
import { hasPermission } from '@/utils/permission'
import model from '@/router/modules/model'
</script>
<style scoped>
.settings-tabs {
  padding: 0 clamp(16px, 3vw, 40px);
  display: flex;
  align-items: center;
  gap: 22px;
  height: 48px;
  overflow-x: auto;
  white-space: nowrap;
  border-bottom: 1px solid var(--el-border-color-light);
  background: white;
}
.settings-tabs a {
  display: inline-flex;
  align-items: center;
  height: 100%;
  text-decoration: none;
  border-bottom: 2px solid transparent;
  color: var(--el-text-color-regular);
}
.settings-tabs .router-link-active {
  border-color: var(--studio-ink);
  color: var(--studio-ink);
  font-weight: 600;
}
.settings-content {
  height: calc(100% - 49px);
  overflow: auto;
}
</style>
