export const mediaNodes = import.meta.glob(
  './nodes/{speech-to-text-node,text-to-speech-node,image-generate,image-to-video,text-to-video,video-understand}/index.ts',
  { eager: true },
)
