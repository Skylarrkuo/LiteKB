import { hasPermission, set_next_route } from '@/utils/permission/index'
import { getChildRouteList } from '@/router/common'
import { shallowRef } from 'vue'
import { getPermissionRoute } from '@/router/common'
import {
  createRouter,
  createWebHistory,
  type NavigationGuardNext,
  type RouteLocationNormalized,
  type RouteRecordName,
} from 'vue-router'
import useStore from '@/stores'
import { installPageSlide } from './page-slide'
import { routes } from '@/router/routes'
export const pendingRoute = shallowRef<RouteLocationNormalized>()
const router = createRouter({
  history: createWebHistory(window.MaxKB?.prefix ? window.MaxKB?.prefix : import.meta.env.BASE_URL),
  routes: routes,
})

function finishProgress(to: RouteLocationNormalized) {
  if (to === pendingRoute.value) pendingRoute.value = undefined
}

// 路由前置拦截器
router.beforeEach(
  async (to: RouteLocationNormalized, from: RouteLocationNormalized, next: NavigationGuardNext) => {
    pendingRoute.value = to
    if (to.name === '404') {
      next()
      return
    }
    const { user, login } = useStore()

    const notAuthRouteNameList = ['login', 'ForgotPassword', 'ResetPassword']
    if (!notAuthRouteNameList.includes(to.name ? to.name.toString() : '')) {
      if (to.query && to.query.token) {
        localStorage.setItem('token', to.query.token.toString())
      }
      const token = login.getToken()
      if (!token) {
        next({
          path: '/login',
        })
        return
      }
      if (!user.userInfo) {
        await user.profile()
      }
    }
    set_next_route(to)
    // 判断是否有菜单权限
    if (to.meta.permission ? hasPermission(to.meta.permission as any, 'OR') : true) {
      if(to.name=='noPermissionD'){
         const n = getPermissionRoute(routes, to)
         if(n.name=='noPermission'){
          next()
          return
         }else{
          next(n)
          return
         }
      }else{
        next()
      }
    } else {
      const n = getPermissionRoute(routes, to)
      next(n)
    }
  },
)
installPageSlide(router)
router.afterEach(finishProgress)
router.onError((_error, to) => finishProgress(to))
export const getChildRouteListByPathAndName = (path: any, name?: RouteRecordName | any) => {
  return getChildRouteList(routes, path, name)
}

export default router
