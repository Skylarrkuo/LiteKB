import { computed, reactive } from 'vue'
import { get, put } from '@/request'

export interface Branding {
  name: string
  icon: string
}

export const branding = reactive<Branding>({ name: 'LiteKB', icon: '' })
export const defaultIcon = (window.MaxKB?.prefix || '/admin') + '/litekb.svg'
export const brandIcon = computed(() => branding.icon || defaultIcon)

function apply(data: Branding) {
  Object.assign(branding, data)
  document.title = branding.name
  const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
  if (link) link.href = brandIcon.value
}

export async function loadBranding() {
  const response = await get('/branding')
  apply(response.data)
}

export async function saveBranding(data: Branding) {
  const response = await put('/branding', data)
  apply(response.data)
}
