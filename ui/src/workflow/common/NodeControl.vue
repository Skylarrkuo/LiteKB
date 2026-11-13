<template>
  <div class="canvas-tools" role="group" :aria-label="$t('common.operation')">
    <button type="button" :aria-label="t('selectNodes')" :title="t('selectNodes')" :aria-pressed="isDrag" @click="changeCursor(true)">
      <el-icon><Position /></el-icon>
    </button>
    <button type="button" :aria-label="t('panCanvas')" :title="t('panCanvas')" :aria-pressed="!isDrag" @click="changeCursor(false)">
      <AppIcon iconName="app-raisehand" :size="16" />
    </button>
    <el-divider direction="vertical" />
    <button type="button" :aria-label="$t('workflow.control.zoomOut')" :title="$t('workflow.control.zoomOut')" @click="zoomOut">
      <el-icon><ZoomOut /></el-icon>
    </button>
    <button type="button" :aria-label="$t('workflow.control.zoomIn')" :title="$t('workflow.control.zoomIn')" @click="zoomIn">
      <el-icon><ZoomIn /></el-icon>
    </button>
    <button type="button" :aria-label="$t('workflow.control.fitView')" :title="$t('workflow.control.fitView')" @click="fitView">
      <AppIcon iconName="app-fitview" />
    </button>
    <el-divider direction="vertical" />
    <button type="button" :aria-label="$t('workflow.control.retract')" :title="$t('workflow.control.retract')" @click="retract">
      <AppIcon iconName="app-retract" />
    </button>
    <button type="button" :aria-label="$t('workflow.control.extend')" :title="$t('workflow.control.extend')" @click="extend">
      <AppIcon iconName="app-extend" />
    </button>
    <button type="button" :aria-label="$t('workflow.control.beautify')" :title="$t('workflow.control.beautify')" @click="layout">
      <AppIcon iconName="app-beautify" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n({
  useScope: 'local',
  messages: {
    'zh-CN': { selectNodes: '框选节点', panCanvas: '移动画布' },
    'zh-Hant': { selectNodes: '框選節點', panCanvas: '移動畫布' },
    'en-US': { selectNodes: 'Select nodes', panCanvas: 'Pan canvas' },
  },
})
const props = defineProps({
  lf: Object || String || null,
})

const isDrag = ref(false)

function zoomIn() {
  props.lf?.zoom(true, [0, 0])
}
function zoomOut() {
  props.lf?.zoom(false, [0, 0])
}
function fitView() {
  props.lf?.resetZoom()
  props.lf?.resetTranslate()
  props.lf?.fitView()
}
const layout = () => {
  props.lf?.extension.dagre.layout()
  props.lf?.graphModel.nodes.forEach((node: any) => {
    if (node.type === 'loop-body-node') {
      node?.loopLayout?.()
    }
  })
}
const retract = () => {
  props.lf?.graphModel.nodes.forEach((element: any) => {
    element.properties.showNode = false
  })
}
const extend = () => {
  props.lf?.graphModel.nodes.forEach((element: any) => {
    element.properties.showNode = true
  })
}
const changeCursor = (bool: boolean) => {
  const element = props.lf?.container.querySelector('.lf-drag-able')
  isDrag.value = bool
  if (bool) {
    if (element) element.style.cursor = 'crosshair'
    props.lf?.openSelectionSelect()
    props.lf?.extension.selectionSelect.setSelectionSense(true, false)
  } else {
    if (element) element.style.cursor = 'grab'
    props.lf?.closeSelectionSelect()
  }
}
</script>
<style scoped lang="scss">
.canvas-tools {
  display: flex;
  align-items: center;
  gap: 2px;
  width: max-content;
  box-sizing: border-box;
  padding: 5px;
  border: 1px solid var(--studio-hairline);
  border-radius: 14px;
  background: var(--app-view-bg-color);
  box-shadow: var(--studio-shadow);
  overflow-x: auto;
  button {
    display: grid;
    place-items: center;
    flex: none;
    width: 32px;
    height: 32px;
    padding: 0;
    border: 0;
    border-radius: 8px;
    color: var(--studio-ink);
    background: transparent;
    font-size: 16px;
    cursor: pointer;
    &:hover { background: var(--studio-selection); }
    &[aria-pressed='true'] { background: var(--studio-ink); color: var(--studio-mint); }
    &:focus-visible { outline-offset: -2px; }
  }
  :deep(.el-divider) { margin-inline: 4px; }
}
</style>
