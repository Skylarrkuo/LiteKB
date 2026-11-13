export interface CatalogTool {
  id: string
  name: string
  description?: string
  desc?: string
  label?: string
  labels?: string[]
  tags?: string[]
  readMe?: string
  tool_type?: string
  icon?: string
  version?: string
  versions?: { name: string }[]
}
export interface CatalogTag {
  key: string
  name: string
  locales?: Record<string, string>
}

export function filterCatalog(tools: CatalogTool[], query: string, category: string) {
  const term = query.trim().toLowerCase()
  return tools.filter(tool => {
    const labels = tool.labels?.length ? tool.labels : [tool.label || 'other']
    return (!category || labels.includes(category)) &&
      (!term || [tool.name, tool.id, tool.description || tool.desc, ...(tool.tags || [])]
        .some(value => value?.toLowerCase().includes(term)))
  })
}
