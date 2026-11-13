export function hasStartupValue(tool: { init_params?: Record<string, unknown> }, field: {
  field: string
  default_value?: unknown
}) {
  const values = tool.init_params ?? {}
  const value = Object.prototype.hasOwnProperty.call(values, field.field) ? values[field.field] : field.default_value
  return value !== undefined && value !== null && !(typeof value === 'string' && !value.trim()) &&
    !(typeof value === 'object' && !Object.keys(value).length)
}
