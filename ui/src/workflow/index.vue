<template>
  <div ref="canvas" class="workflow-app"></div>
  <el-alert v-if="unavailable.length" class="missing-nodes" type="warning" :closable="false"
    :title="$t('studio.unavailableNodes') + ' · ' + unavailable.join(', ')" />
  <!-- 辅助工具栏 -->
  <Control class="workflow-control" v-if="lf" :lf="lf"></Control>
  <TeleportContainer :flow-id="flowId"/>
  <NodeSearch :lf="lf" ref="nodeSearchRef"></NodeSearch>
</template>
<script setup lang="ts">
import LogicFlow from '@logicflow/core'
import {ref, onMounted, onUnmounted, inject, nextTick} from 'vue'
import AppEdge from './common/edge'
import loopEdge from './common/loopEdge'
import Control from './common/NodeControl.vue'
import {SelectionSelect} from '@logicflow/extension'
import '@logicflow/extension/lib/style/index.css'
import '@logicflow/core/dist/style/index.css'
import {initDefaultShortcut} from '@/workflow/common/shortcut'
import Dagre from '@/workflow/plugins/dagre'
import {disconnectAll, getTeleport} from '@/workflow/common/teleport'
import {WorkflowMode} from '@/enums/application'

import NodeSearch from '@/workflow/common/NodeSearch.vue'

import { disabledGraphNodes } from '@/workflow/capabilities'
import { t } from '@/locales'
import { shallowRef } from 'vue'
import { installedNodes } from '@/workflow/registry'
const workflow_mode = inject('workflowMode') || WorkflowMode.Application
const loop_workflow_mode = inject('loopWorkflowMode') || WorkflowMode.ApplicationLoop
const nodeSearchRef = ref<InstanceType<typeof NodeSearch>>()
defineOptions({name: 'WorkFlow'})
const TeleportContainer = getTeleport()
const flowId = ref('')
type ShapeItem = {
  type?: string
  text?: string
  icon?: string
  label?: string
  className?: string
  disabled?: boolean
  properties?: Record<string, any>
  callback?: (lf: LogicFlow, container?: HTMLElement) => void
}

const props = defineProps({
  data: Object || null,
})

const canvas = ref<HTMLElement>()
const lf = ref()
let canvasSize: ResizeObserver | undefined
onMounted(() => {
  renderGraphData()
  if (canvas.value) {
    canvasSize = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      if (width && height) lf.value?.resize(width, height)
    })
    canvasSize.observe(canvas.value)
  }
})
onUnmounted(() => {
  canvasSize?.disconnect()
  disconnectAll()
})
const unavailable = ref<string[]>([])
const preservedGraph = shallowRef()
const render = (data: any) => {
  unavailable.value = disabledGraphNodes(data)
  preservedGraph.value = unavailable.value.length ? data : undefined
  lf.value.render(preservedGraph.value ? { nodes: [], edges: [] } : data)
}

const renderGraphData = (data?: any) => {
  const container = canvas.value
  if (lf.value && data) {
    render(data)
    return
  }
  if (container) {
    lf.value = new LogicFlow({
      plugins: [Dagre, SelectionSelect],
      textEdit: false,
      adjustEdge: false,
      adjustEdgeStartAndEnd: false,
      background: {
        backgroundColor: 'var(--app-layout-bg-color)',
      },
      grid: {
        size: 10,
        type: 'dot',
        config: {
          color: 'var(--studio-hairline)',
          thickness: 1,
        },
      },
      keyboard: {
        enabled: true,
      },
      isSilentMode: false,
      container: container,
    })
    lf.value.setTheme({
      bezier: {
        stroke: 'var(--app-text-color-secondary)',
        strokeWidth: 1,
      },
    })
    lf.value.on('graph:rendered', () => {
      flowId.value = lf.value.graphModel.flowId
    })
    lf.value.on('node:delete', () => {
      nodeSearchRef.value?.reSearch()
    })
    initDefaultShortcut(lf.value, lf.value.graphModel)
    lf.value.batchRegister([
      ...installedNodes(),
      AppEdge,
      loopEdge,
    ])

    lf.value.setDefaultEdgeType('app-edge')

    render(data || {})
    lf.value.graphModel.get_provide = (node: any, graph: any) => {
      return {
        getNode: () => node,
        getGraph: () => graph,
        workflowMode: workflow_mode,
        loopWorkflowMode: loop_workflow_mode,
      }
    }
    lf.value.graphModel.eventCenter.on('delete_edge', (id_list: Array<string>) => {
      id_list.forEach((id: string) => {
        lf.value.deleteEdge(id)
      })
    })
    lf.value.graphModel.eventCenter.on('anchor:drop', (data: any) => {
      // 清除当前节点下面的子节点的所有缓存
      data.nodeModel.clear_next_node_field(false)
    })

    setTimeout(() => {
      if (lf.value.graphModel?.nodes.length > 1) {
        lf.value?.fitView()
      } else {
        lf.value?.translateCenter()
      }
    }, 500)
  }
}

const validate = () => {
  if (preservedGraph.value) return Promise.reject({ errMessage: t('studio.unavailableNodes') })
  return Promise.all(lf.value.graphModel.nodes.map((element: any) => element?.validate?.()))
}
const getGraphData = () => {
  if (preservedGraph.value) return preservedGraph.value
  const graph_data = lf.value.getGraphData()
  graph_data.nodes.forEach((node: any) => {
    if (node.type === 'loop-body-node') {
      const node_model = lf.value.getNodeModelById(node.id)
      node_model.set_loop_body()
    }
  })
  const _graph_data = lf.value.getGraphData()
  _graph_data.nodes = _graph_data.nodes.filter((node: any) => node.type !== 'loop-body-node')
  _graph_data.edges = graph_data.edges.filter((node: any) => node.type !== 'loop-edge')
  return _graph_data
}

const onmousedown = (shapeItem: ShapeItem) => {
  if (preservedGraph.value) return
  if (shapeItem.type) {
    lf.value.dnd.startDrag({
      type: shapeItem.type,
      properties: {...shapeItem.properties},
    })
  }

  if (shapeItem.callback) {
    shapeItem.callback(lf.value)
  }
}
const addNode = (shapeItem: ShapeItem) => {
  if (preservedGraph.value) return
  lf.value.clearSelectElements()
  const { graphModel, container } = lf.value
  const [x, y] = graphModel.transformModel.HtmlPointToCanvasPoint([
    container.clientWidth / 2,
    container.clientHeight / 2,
  ])
  const newNode = lf.value.graphModel.addNode({
    type: shapeItem.type,
    properties: shapeItem.properties,
    x,
    y,
  })
  newNode.isSelected = true
  newNode.isHovered = true
  lf.value.toFront(newNode.id)
}

const clearGraphData = () => {
  return lf.value.clearData()
}
const fitView = () => {
  nextTick(() => {
    lf.value?.fitView()
  })
}

/**
 * 定位并高亮画布上的问题节点(发布/节点校验失败时调用,配合外层 MsgError 使用)。
 * 支持顶层节点与 loop 嵌套节点:嵌套节点会先定位到所属顶层 loop 节点。
 * @param node graph_data 中的节点(含 id)
 */
const highlightNode = (node: any) => {
  const graphModel = lf.value?.graphModel
  if (!graphModel || !node?.id) return
  const nodeModel = graphModel.getNodeModelById(node.id)
  if (nodeModel) {
    graphModel.selectNodeById(node.id)
    graphModel.transformModel.focusOn(nodeModel.x, nodeModel.y, graphModel.width, graphModel.height)
    return
  }
  // 节点位于 loop-body 内时,定位到所属顶层 loop 节点
  for (const topNode of graphModel.nodes || []) {
    const loopBody = (topNode.properties?.node_data || {}).loop_body?.nodes || []
    if (loopBody.some((n: any) => n.id === node.id)) {
      graphModel.selectNodeById(topNode.id)
      graphModel.transformModel.focusOn(topNode.x, topNode.y, graphModel.width, graphModel.height)
      return
    }
  }
}

defineExpose({
  onmousedown,
  isReadOnly: () => Boolean(preservedGraph.value),
  validate,
  getGraphData,
  addNode,
  clearGraphData,
  renderGraphData,
  render,
  fitView,
  highlightNode,
})
</script>
<style scoped>
.missing-nodes { position: absolute; top: 56px; left: 16px; width: auto; max-width: 90%; z-index: 5; }
</style>
<style scoped lang="scss">
.workflow-app {
  width: 100%;
  height: 100%;
  position: relative;
}

.workflow-control {
  position: absolute;
  bottom: 16px;
  left: 16px;
  max-width: calc(100% - 32px);
  z-index: 2;
}

.workflow-app :deep(.lf-drag-able) {
  cursor: grab;
}
</style>
