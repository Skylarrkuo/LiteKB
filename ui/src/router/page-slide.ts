import { nextTick } from 'vue'
import type { Router, RouteLocationNormalized } from 'vue-router'
import { topMenuRoutes } from './routes'

function surface(settingsTab: boolean) {
  return (settingsTab && document.querySelector<HTMLElement>('.settings-content')) ||
    document.querySelector<HTMLElement>('.studio-main-content') ||
    document.querySelector<HTMLElement>('.route-page')
}

export function installPageSlide(router: Router) {
  const root = document.documentElement
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)')
  let position = window.history.state?.position
  let active: { to: RouteLocationNormalized; finish: () => void; skip: () => void } | undefined
  let fallback: Animation | undefined

  function direction(to: RouteLocationNormalized, from: RouteLocationNormalized) {
    const menuIndex = (route: RouteLocationNormalized) =>
      topMenuRoutes.findIndex(menu => menu.path === route.meta.activeMenu)
    const source = menuIndex(from)
    const target = menuIndex(to)
    if (source >= 0 && target >= 0 && source !== target) return Math.sign(target - source)
    const parent = to.matched[to.matched.length - 2]
    if (parent && from.matched.includes(parent)) {
      const tab = (route: RouteLocationNormalized) => parent.children.findIndex(child => child.name === route.name)
      const a = tab(to), b = tab(from)
      if (a >= 0 && b >= 0 && a !== b) return Math.sign(a - b)
    }
    const depth = to.path.split('/').length - from.path.split('/').length
    return Math.sign(depth) || (window.history.state?.position < position ? -1 : 1)
  }

  router.beforeEach(() => {
    active?.skip()
    fallback?.cancel()
  })

  // Capture only after guards and lazy imports finish. The snapshot holds the outgoing page
  // while Vue replaces it, including when the two routes use different layouts.
  router.beforeResolve((to, from) => {
    if (!from.name || to.path === from.path || reduce.matches || document.hidden ||
        typeof document.startViewTransition !== 'function') return
    const tabs = to.meta.activeMenu === '/settings' && from.meta.activeMenu === '/settings'
    const old = surface(tabs)
    if (!old) return
    const side = direction(to, from)
    const marked = [old]
    old.style.viewTransitionName = 'studio-page'
    root.dataset.slide = side > 0 ? 'forward' : 'back'
    let captured!: () => void
    const readyToNavigate = new Promise<void>(resolve => { captured = resolve })
    let finish!: () => void
    const committed = new Promise<void>(resolve => { finish = resolve })
    const transition = document.startViewTransition(async () => {
      captured()
      await committed
      await nextTick()
      if (active?.to !== to) return
      const incoming = surface(tabs)
      if (incoming && incoming !== old) {
        old.style.removeProperty('view-transition-name')
        incoming.style.viewTransitionName = 'studio-page'
        marked.push(incoming)
      }
    })
    function cleanup() {
      if (active?.to !== to) return
      for (const el of marked) el.style.removeProperty('view-transition-name')
      delete root.dataset.slide
      active = undefined
    }
    function skip() {
      transition.skipTransition()
      captured()
      finish()
      cleanup()
    }
    active = { to, finish, skip }
    void transition.ready.catch(() => {})
    void transition.finished.then(cleanup, cleanup)
    return readyToNavigate
  })

  router.afterEach((to, from, failure) => {
    if (active?.to === to) {
      if (failure) active.skip()
      else active.finish()
    } else if (!failure && from.name && to.path !== from.path && !reduce.matches &&
               typeof document.startViewTransition !== 'function') {
      const side = direction(to, from)
      void nextTick(() => {
        if (router.currentRoute.value !== to) return
        const page = surface(to.meta.activeMenu === '/settings' && from.meta.activeMenu === '/settings')
        fallback = page?.animate([
          { transform: 'translateX(' + side * 32 + 'px)', opacity: .75 },
          { transform: 'translateX(0)', opacity: 1 },
        ], { duration: 230, easing: 'cubic-bezier(.22,.68,.22,1)' })
      })
    }
    if (!failure) position = window.history.state?.position
  })
  router.onError((_error, to) => { if (active?.to === to) active.skip() })
}
