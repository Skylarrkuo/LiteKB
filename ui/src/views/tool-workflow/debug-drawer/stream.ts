export interface WorkflowFrame {
  chat_id?: string
  chat_record_id?: string
  id?: string
  content?: string
  is_end?: boolean
  [key: string]: unknown
}

/** Decode complete SSE events across arbitrary byte boundaries (including inside UTF-8 characters). */
export async function readWorkflowEvents(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  consume: (frame: WorkflowFrame) => void,
): Promise<boolean> {
  const decoder = new TextDecoder()
  let pending = ''
  while (true) {
    const { done, value } = await reader.read()
    pending += decoder.decode(value, { stream: !done })
    let boundary = /\r?\n\r?\n/.exec(pending)
    while (boundary) {
      const event = pending.slice(0, boundary.index)
      pending = pending.slice(boundary.index + boundary[0].length)
      const data = event
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).replace(/^ /, ''))
        .join('\n')
      if (data) {
        const frame: WorkflowFrame = JSON.parse(data)
        consume(frame)
        if (frame.is_end) return true
      }
      boundary = /\r?\n\r?\n/.exec(pending)
    }
    if (done) return false
  }
}
