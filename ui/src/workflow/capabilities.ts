import { computed, ref } from 'vue'
import { get } from '@/request'

const installedMedia = import.meta.env.VITE_LITEKB_MEDIA_NODES === '1'
const enabledMedia = ref(false)
const disabled = ref<string[]>(['data-source-web-node'])
const mediaTypes = new Set([
  'speech-to-text-node',
  'text-to-speech-node',
  'image-generate-node',
  'image-to-video-node',
  'text-to-video-node',
  'video-understand-node',
])

export const mediaEnabled = computed(() => installedMedia && enabledMedia.value)
export const mediaModelsEnabled = computed(() => enabledMedia.value)

export function nodeEnabled(type: string) {
  return (
    !disabled.value.includes(type) &&
    type !== 'data-source-web-node' &&
    (mediaEnabled.value || !mediaTypes.has(type))
  )
}

export async function loadCapabilities() {
  const response = await get('/capabilities', undefined, undefined, 5000)
  enabledMedia.value = response.data.media_nodes === true
  disabled.value = response.data.disabled_nodes
}

interface SavedGraph {
  nodes?: Array<{
    type: string
    properties?: { node_data?: { loop_body?: SavedGraph }; workflow?: SavedGraph }
  }>
}

export function disabledGraphNodes(graph?: SavedGraph): string[] {
  const types = new Set<string>()
  for (const node of graph?.nodes || []) {
    if (!nodeEnabled(node.type)) types.add(node.type)
    for (const body of [node.properties?.node_data?.loop_body, node.properties?.workflow]) {
      disabledGraphNodes(body).forEach((type) => types.add(type))
    }
  }
  return [...types]
}
