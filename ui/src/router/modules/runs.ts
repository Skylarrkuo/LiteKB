import { RoleConst } from '@/utils/permission/data'

export default {
  path: '/runs',
  name: 'runs',
  redirect: { name: 'run-list' },
  meta: {
    title: 'studio.runs',
    icon: 'app-history-outlined',
    menu: true,
    order: 5,
    group: 'workspace',
    permission: [RoleConst.ADMIN],
  },
  component: () => import('@/layout/layout-template/SimpleLayout.vue'),
  children: [
    {
      path: '',
      name: 'run-list',
      meta: { activeMenu: '/runs', permission: [RoleConst.ADMIN] },
      component: () => import('@/views/studio/Runs.vue'),
    },
  ],
}
