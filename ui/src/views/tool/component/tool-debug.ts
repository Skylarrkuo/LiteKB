import { cloneDeep } from 'lodash'
import type { FormField } from '@/components/dynamics-form/type'

export interface ToolInput {
  name: string
  type?: string
  is_required?: boolean
  desc?: string
  value?: unknown
  default_value?: unknown
}
export interface ToolDefinition {
  id?: string
  name?: string
  code?: string
  input_field_list?: ToolInput[]
  init_field_list?: FormField[]
  init_params?: Record<string, unknown>
  execution?: { debug_mode: string; available: boolean; reason?: string }
}
export type DebugResult = { ok: boolean; output: unknown }

export function initialParams(
  fields: FormField[],
  saved: Record<string, unknown> = {},
  draft = false,
) {
  const entries: [string, unknown][] = []
  for (const item of fields) {
    if (draft && item.input_type === 'PasswordInput') continue
    if (Object.prototype.hasOwnProperty.call(saved, item.field))
      entries.push([item.field, saved[item.field]])
    else if (item.show_default_value !== false && item.default_value !== undefined)
      entries.push([item.field, item.default_value])
  }
  return cloneDeep(Object.fromEntries(entries))
}

export function inputText(value: unknown): string {
  if (value == null) return ''
  return typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
}
export function validInput(type: string | undefined, value: string) {
  if (!value.trim()) return true
  if (type === 'int') return /^[+-]?\d+$/.test(value.trim())
  if (type === 'float')
    return (
      /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim()) &&
      Number.isFinite(Number(value))
    )
  if (type === 'boolean') return value === 'true' || value === 'false'
  if (type === 'dict' || type === 'array') {
    try {
      const parsed = JSON.parse(value)
      return type === 'dict'
        ? parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed)
        : Array.isArray(parsed)
    } catch {
      return false
    }
  }
  return true
}
export function errorMessage(error: unknown, fallback: string) {
  const e = error as { response?: { data?: { message?: unknown } }; message?: unknown }
  const message = e?.response?.data?.message || e?.message
  return typeof message === 'string' && message.trim() ? message : fallback
}
export function formatOutput(value: unknown): string {
  if (typeof value === 'string') return value === '' ? '""' : value
  return JSON.stringify(value, null, 2) ?? '—'
}
