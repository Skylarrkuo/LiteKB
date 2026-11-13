import { mediaNodes } from '@litekb-media-nodes'
import { nodeEnabled } from './capabilities'

const coreNodes = import.meta.glob<{ default: { type: string } }>(
  [
    './nodes/**/index.ts',
    '!./nodes/{data-source-web-node,speech-to-text-node,text-to-speech-node,image-generate,image-to-video,text-to-video,video-understand}/index.ts',
  ],
  { eager: true },
)

export function installedNodes() {
  return Object.values({ ...coreNodes, ...mediaNodes })
    .map((module) => module.default)
    .filter((node) => nodeEnabled(node.type))
}
