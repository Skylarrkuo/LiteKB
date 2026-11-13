import { RoleConst } from '@/utils/permission/data'
import model from './model'
import { hasPermission } from '@/utils/permission'

export default {
  path: '/settings',
  name: 'settings',
  meta: {
    title: 'common.setting',
    menu: true,
    icon: 'app-setting',
    group: 'workspace',
    order: 6,
    permission: [...model.meta.permission, RoleConst.ADMIN],
  },
  redirect: () =>
    hasPermission(model.meta.permission, 'OR') ? '/settings/models' : '/settings/branding',
  component: () => import('@/layout/layout-template/SimpleLayout.vue'),
  children: [
    {
      path: '',
      component: () => import('@/views/studio/SettingsLayout.vue'),
      children: [
        {
          path: 'models',
          name: 'model-index',
          meta: { activeMenu: '/settings', permission: model.meta.permission },
          component: () => import('@/views/model/index.vue'),
        },
        {
          path: 'branding',
          name: 'branding',
          meta: { activeMenu: '/settings', permission: [RoleConst.ADMIN] },
          component: () => import('@/views/studio/Branding.vue'),
        },
        {
          path: 'accounts',
          name: 'accounts',
          meta: { activeMenu: '/settings', permission: [RoleConst.ADMIN] },
          component: () => import('@/views/system/user-manage/index.vue'),
        },
      ],
    },
  ],
}
