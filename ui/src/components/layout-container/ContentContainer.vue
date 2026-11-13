<template>
  <div class="content-container">
    <div class="content-container__header flex align-center w-full" v-if="slots.header || header">
      <slot name="backButton">
        <back-button :to="backTo" v-if="showBack"></back-button>
      </slot>
      <div class="content-toolbar flex-between w-full">
        <slot name="header">
          <h2>{{ header }}</h2>
        </slot>
        <slot name="search"> </slot>
      </div>
    </div>

    <div class="content-container__main">
      <el-scrollbar class="content-scroll">
        <slot></slot>
      </el-scrollbar>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, useSlots } from 'vue'
defineOptions({ name: 'ContentContainer' })
const slots = useSlots()
const props = defineProps({
  header: String || null,
  backTo: String,
})
const showBack = computed(() => {
  const { backTo } = props
  return backTo
})
</script>

<style lang="scss" scoped>
.content-container {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  .content-container__header {
    box-sizing: border-box;
    padding: 22px clamp(16px, 2.4vw, 32px) 14px;
    flex-wrap: wrap;
    flex-shrink: 0;
    .content-toolbar {
      align-items: center;
      gap: 12px;
      min-width: 0;
      flex-wrap: wrap;
    }
    :deep(h2),
    :deep(h4) {
      font-size: 22px;
      line-height: 1.25;
      font-weight: 650;
      letter-spacing: -0.035em;
    }
  }
  .content-container__main {
    flex: 1;
    min-height: 0;
    box-sizing: border-box;
    min-width: 0;
    .content-scroll {
      padding: 0 clamp(16px, 2.4vw, 32px) 16px;
      box-sizing: border-box;
    }
  }
}
@media (max-width: 760px) {
  .content-container .content-toolbar {
    :deep(> .flex) {
      width: 100%;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }
    :deep(.complex-search) {
      display: inline-flex;
      min-width: 0;
      max-width: 100%;
      .el-input,
      .el-select {
        min-width: 0;
      }
    }
    :deep(.ml-8),
    :deep(.ml-16) {
      margin-left: 0;
    }
  }
}
</style>
