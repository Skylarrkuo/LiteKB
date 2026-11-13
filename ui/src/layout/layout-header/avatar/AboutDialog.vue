<template>
  <el-dialog
    v-model="visible"
    append-to-body
    align-center
    :title="$t('layout.about.title')"
    class="about-project-dialog"
    width="min(510px, calc(100vw - 28px))"
    @opened="heading?.focus({ preventScroll: true })"
    @closed="emit('closed')"
  >
    <template #header="{ titleId, titleClass }">
      <h2 :id="titleId" ref="heading" :class="titleClass" tabindex="-1">{{ $t('layout.about.title') }}</h2>
    </template>
    <div class="about-project">
      <div class="project-brand">
        <LogoFull height="34px" />
        <span v-if="user.version" class="version">{{ $t('layout.about.version') }} {{ user.version }}</span>
      </div>
      <p>{{ $t('layout.about.projectIntro') }}</p>
      <dl class="project-links">
        <div>
          <dt>{{ $t('layout.about.maintainer') }}</dt>
          <dd>Skylarrkuo</dd>
        </div>
        <div>
          <dt>{{ $t('layout.about.repository') }}</dt>
          <dd><a href="https://github.com/Skylarrkuo/LiteKB" target="_blank" rel="noopener noreferrer">Skylarrkuo/LiteKB <el-icon aria-hidden="true"><TopRight /></el-icon></a></dd>
        </div>
      </dl>
      <section class="upstream">
        <h3>{{ $t('layout.about.upstream') }}</h3>
        <p>{{ $t('layout.about.credits') }}</p>
        <div class="source-links">
          <a href="https://github.com/1Panel-dev/MaxKB" target="_blank" rel="noopener noreferrer">1Panel-dev/MaxKB <el-icon aria-hidden="true"><TopRight /></el-icon></a>
          <a href="https://github.com/Skylarrkuo/LiteKB/blob/HEAD/LICENSE" target="_blank" rel="noopener noreferrer">{{ $t('layout.about.license') }} <el-icon aria-hidden="true"><TopRight /></el-icon></a>
        </div>
      </section>
    </div>
  </el-dialog>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import useStore from '@/stores'
const visible = defineModel<boolean>({ required: true })
const emit = defineEmits<{ closed: [] }>()
const heading = ref<HTMLHeadingElement>()
const { user } = useStore()
</script>
<style scoped>
.about-project { display: grid; gap: 16px; overflow-wrap: anywhere; }
.project-brand, .source-links { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px; }
.version { color: var(--app-text-color-secondary); font-size: 12px; font-variant-numeric: tabular-nums; }
.about-project p { margin: 0; line-height: 1.65; }
.project-links { margin: 0; padding: 4px 14px; border-radius: var(--app-border-radius-base); background: var(--app-layout-bg-color); }
.project-links > div { display: grid; grid-template-columns: minmax(90px, 1fr) minmax(0, 1.6fr); gap: 12px; align-items: baseline; padding-block: 9px; }
.project-links > div + div { border-top: 1px solid var(--studio-hairline); }
.project-links dt { color: var(--app-text-color-secondary); }
.project-links dd { margin: 0; font-weight: 600; }
.upstream h3 { margin-bottom: 4px; font-size: 15px; color: var(--studio-ink); }
.source-links { margin-top: 8px; }
.about-project a { display: inline-flex; align-items: center; gap: 4px; min-height: 26px; color: var(--studio-ink); text-decoration: underline; text-underline-offset: 3px; }
.about-project a:hover { text-decoration-thickness: 2px; }
:global(.el-dialog.about-project-dialog) { max-height: calc(100dvh - 28px); overflow-y: auto; }
</style>
