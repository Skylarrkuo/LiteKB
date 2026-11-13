export interface RunRow {
  id: string
  agent_id: string
  version_id: string
  client_id: string
  subject: string
  session_id: string
  chat_record_id: string | null
  status: string
  event_sequence: number
  budget: { max_runtime_seconds?: number; used_runtime_seconds?: number }
  error: string
  created_at: string
  updated_at: string
}

export interface RunStep {
  node_id: string
  node_type: string
  execution_path: (string | number)[]
  iteration: number | null
  status: string
  attempt: number
  elapsed_seconds: number
  output_ref: Record<string, unknown>
}

export interface RunEvent {
  sequence: number
  kind: string
  data: Record<string, unknown>
  created_at: string
}

export interface RunDetail extends RunRow {
  steps: RunStep[]
  events: RunEvent[]
  result: {
    answer?: string
    usage?: { input_tokens: number; output_tokens: number }
    sources?: Record<string, unknown>[]
    waiting_step?: (string | number)[]
    [key: string]: unknown
  }
}

export function isActiveRun(status: string) {
  return ['queued', 'running', 'waiting_input'].includes(status)
}

// The backend persists steps by traversing JSONB. Only step.started describes their start order.
export function orderedSteps(steps: RunStep[], events: RunEvent[]): RunStep[] {
  const byNode = new Map<string, number[]>()
  steps.forEach((step, i) => {
    const indices = byNode.get(step.node_id)
    if (indices) indices.push(i)
    else byNode.set(step.node_id, [i])
  })
  const starts = new Map<string, RunEvent[]>()
  for (const event of events) {
    const node = event.data.node_id
    if (event.kind !== 'step.started' || typeof node !== 'string' || !byNode.has(node)) continue
    const list = starts.get(node)
    if (list) list.push(event)
    else starts.set(node, [event])
  }
  const sequence = new Map<number, number>()
  for (const [node, nodeStarts] of starts) {
    const indices = byNode.get(node)!
    if (indices.length === 1 && nodeStarts.length === 1) {
      const event = nodeStarts[0]
      const path = steps[indices[0]].execution_path
      const leaf = path?.[path.length - 1]
      // Older records may lack one identifier. The node alone must be unique on both sides.
      if (!event.data.runtime_node_id || leaf == null || leaf === event.data.runtime_node_id) {
        sequence.set(indices[0], event.sequence)
      }
      continue
    }
    const byRuntime = new Map<string, number[]>()
    for (const i of indices) {
      const path = steps[i].execution_path
      const leaf = path?.[path.length - 1]
      if (typeof leaf !== 'string') continue
      const peers = byRuntime.get(leaf)
      if (peers) peers.push(i)
      else byRuntime.set(leaf, [i])
    }
    for (const [runtimeId, peers] of byRuntime) {
      const matches = nodeStarts.filter((e) => e.data.runtime_node_id === runtimeId)
      if (!matches.length || matches.length !== peers.length) continue
      // A shared leaf in distinct loop/child paths cannot identify an iteration. Retries of
      // one full path can be paired only when all attempts have corresponding starts.
      if (
        peers.length > 1 &&
        (new Set(peers.map((i) => JSON.stringify(steps[i].execution_path))).size !== 1 ||
          new Set(peers.map((i) => steps[i].attempt)).size !== peers.length)
      )
        continue
      peers.sort((a, b) => steps[a].attempt - steps[b].attempt)
      matches.sort((a, b) => a.sequence - b.sequence)
      peers.forEach((i, j) => sequence.set(i, matches[j].sequence))
    }
  }
  // Missing starts are normal for forms and for a 200-event window. Keep their slots stable.
  const slots = [...sequence.keys()].sort((a, b) => a - b)
  const ordered = [...slots].sort((a, b) => sequence.get(a)! - sequence.get(b)!)
  const result = [...steps]
  slots.forEach((i, j) => {
    result[i] = steps[ordered[j]]
  })
  return result
}

export function shortId(id: string) {
  return id.length > 20 ? id.slice(0, 8) + '…' + id.slice(-4) : id
}

export function iterations(step: RunStep): number[] {
  const indices: number[] = []
  step.execution_path.forEach((part, index) => {
    if (typeof part === 'number' && step.execution_path[index - 1] === 'loop_node_data')
      indices.push(part + 1)
  })
  if (!indices.length && step.iteration != null) indices.push(step.iteration + 1)
  return indices
}

export function duration(seconds: number, locale: string) {
  if (!Number.isFinite(seconds) || seconds < 0) return '—'
  const ms = seconds > 0 && seconds < 1
  return new Intl.NumberFormat(locale, {
    style: 'unit',
    unit: ms ? 'millisecond' : 'second',
    unitDisplay: 'short',
    maximumFractionDigits: ms ? 0 : 2,
  }).format(ms ? seconds * 1000 : seconds)
}
