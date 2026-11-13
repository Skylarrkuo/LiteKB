<template>
  <div
    class="layout-container flex h-full"
    :class="{
      'layout-container__collapse': isCollapse,
      'responsive-sidebar': showLeft && showCollapse,
      'mobile-open': mobileOpen,
    }"
  >
    <button
      v-if="showLeft && showCollapse"
      type="button"
      class="mobile-sidebar-toggle"
      :aria-expanded="mobileOpen"
      :aria-controls="panelId"
      @click="mobileOpen = !mobileOpen"
    >
      <el-icon aria-hidden="true"><Fold /></el-icon>
      {{ navigationLabel || $t('studio.sidebar') }}
      <el-icon class="disclosure" aria-hidden="true"><ArrowDown /></el-icon>
    </button>
    <div
      :class="`layout-container__left border-r ${isCollapse ? 'hidden' : ''}`"
      :style="{ width: isCollapse ? 0 : `${leftWidth}px` }"
      v-if="showLeft"
    >
      <div :id="panelId" class="layout-container__left_content">
        <slot name="left"></slot>
      </div>
      <el-tooltip
        :content="isCollapse ? $t('common.expand') : $t('common.collapse')"
        placement="right"
        v-if="props.showCollapse"
      >
        <el-button
          class="collapse"
          size="small"
          circle
          :aria-label="isCollapse ? $t('common.expand') : $t('common.collapse')"
          :aria-expanded="!isCollapse"
          :aria-controls="panelId"
          @click="isCollapse = !isCollapse"
          :icon="isCollapse ? 'ArrowRightBold' : 'ArrowLeftBold'"
        />
      </el-tooltip>
      <div
        v-if="props.resizable"
        class="splitter-bar-line"
        :class="isResizing ? 'hover' : ''"
        @mousedown="onSplitterMouseDown"
      ></div>
    </div>
    <div class="layout-container__right">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onUnmounted, ref, useId } from 'vue'
defineOptions({ name: 'LayoutContainer' })

const props = defineProps({
  showCollapse: Boolean,
  resizable: Boolean,
  navigationLabel: String,
  minLeftWidth: {
    type: Number,
    default: 240,
  },
  maxLeftWidth: {
    type: Number,
    default: 400,
  },
  showLeft: {
    type: Boolean,
    default: true,
  },
})

const isCollapse = ref(false)
const mobileOpen = ref(false)
const panelId = useId()
const leftWidth = ref(props.minLeftWidth)
const isResizing = ref(false)

const onSplitterMouseDown = (e: MouseEvent) => {
  if (!props.resizable) return
  e.preventDefault()
  isResizing.value = true
  document.body.style.userSelect = 'none'
  const startX = e.clientX
  const startWidth = leftWidth.value
  const onMouseMove = (moveEvent: MouseEvent) => {
    if (!isResizing.value) return
    const deltaX = moveEvent.clientX - startX
    let newWidth = startWidth + deltaX

    // 限制宽度在最小和最大值之间
    newWidth = Math.max(props.minLeftWidth, Math.min(props.maxLeftWidth, newWidth))
    leftWidth.value = newWidth
  }

  const onMouseUp = () => {
    isResizing.value = false
    document.body.style.userSelect = ''
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

onUnmounted(() => {
  document.removeEventListener('mousemove', () => {})
  document.removeEventListener('mouseup', () => {})
})
</script>

<style lang="scss" scoped>
.layout-container {
  min-height: 0;
  .mobile-sidebar-toggle {
    display: none;
  }
  &__left {
    position: relative;
    box-sizing: border-box;
    // transition: width 0.28s;
    width: var(--sidebar-width);
    flex: none;
    background: #f0f4f1;
    .splitter-bar-line {
      z-index: 1;
      position: absolute;
      top: 0;
      right: 0;
      cursor: col-resize;
      width: 4px;
      height: 100%;
      &.hover:after {
        width: 1px;
        height: 100%;
        content: '';
        z-index: 2;
        position: absolute;
        right: -1px;
        top: 0;
        background: var(--el-color-primary);
      }
    }

    .collapse {
      position: absolute;
      top: 36px;
      right: -12px;
      box-shadow: 0px 5px 10px 0px rgba(var(--el-text-color-primary-rgb), 0.1);
      z-index: 2;
    }

    .layout-container__left_content {
      width: 100%;
      height: 100%;
    }

    &.hidden {
      width: 0;
      min-width: 0;

      .layout-container__left_content {
        visibility: hidden;
      }

      .collapse {
        right: -18px;
      }
    }
  }

  &__right {
    flex: 1;
    min-width: 0;
    min-height: 0;
    overflow: hidden;
  }
  &__collapse {
    :deep(.mul-operation) {
      width: 100% !important;
    }
  }
}
@media (max-width: 760px) {
  .responsive-sidebar {
    flex-direction: column;
    .mobile-sidebar-toggle {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 16px;
      flex: 0 0 38px;
      width: 100%;
      border: 0;
      border-bottom: 1px solid var(--studio-hairline);
      color: var(--studio-ink);
      background: #edf3ef;
      font: inherit;
      text-align: left;
      cursor: pointer;
      &:focus-visible {
        outline-offset: -3px;
      }
      .disclosure {
        margin-left: auto;
      }
    }
    > .layout-container__left {
      display: none;
      width: 100% !important;
      max-height: 35dvh;
      overflow: auto;
      border: 0;
      border-bottom: 1px solid var(--studio-hairline);
      .layout-container__left_content {
        visibility: visible;
      }
      .collapse,
      .splitter-bar-line {
        display: none;
      }
    }
    &.mobile-open {
      > .layout-container__left {
        display: block;
      }
      .disclosure {
        transform: rotate(180deg);
      }
    }
  }
}
</style>
