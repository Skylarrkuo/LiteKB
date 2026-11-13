import type { RouteRecordRaw } from 'vue-router'
import application from './modules/application'
import knowledge from './modules/knowledge'
import tool from './modules/tool'
import system from './modules/system'
import runs from './modules/runs'
import documentRoutes from './modules/document'
import paragraph from './modules/paragraph'
import detail from './modules/application-detail'

export const routes: Array<RouteRecordRaw> = [
  {
    path: '/',
    name: 'root',
    redirect: '/application',
    children: [
      application, knowledge, tool, runs, system, documentRoutes, paragraph, detail,
      { path: '/home', name: 'home', redirect: '/application' },
      { path: '/model', redirect: '/settings/models' },
      {
        path: '/no-permission',
        name: 'noPermission',
        redirect: '/no-permission',
        meta: {},
        children: [
          {
            path: '/no-permission',
            name: 'noPermissionD',
            meta: {},
            component: () => import('@/views/error/NoPermission.vue'),
          },
        ],
        component: () => import('@/layout/layout-template/SimpleLayout.vue'),
      },
    ],
  },

  // 高级编排
  {
    path: '/application/:from/:id/workflow',
    name: 'ApplicationWorkflow',
    meta: { activeMenu: '/application' },
    component: () => import('@/views/application-workflow/index.vue'),
  },
  // 知识库工作流
  {
    path: '/knowledge/:id/:folderId/workflow',
    name: 'KnowledgeWorkflow',
    meta: { activeMenu: '/knowledge' },
    component: () => import('@/views/knowledge-workflow/index.vue'),
  },
  {
    path: '/tool/:id/:folderId/workflow',
    name: 'ToolWorkflow',
    meta: { activeMenu: '/tool' },
    component: () => import('@/views/tool-workflow/index.vue'),
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/login/index.vue'),
  },
  {
    path: '/forgot_password',
    name: 'ForgotPassword',
    component: () => import('@/views/login/ForgotPassword.vue'),
  },
  {
    path: '/reset_password/:code/:email',
    name: 'ResetPassword',
    component: () => import('@/views/login/ResetPassword.vue'),
  },
  {
    path: '/permission',
    name: 'permission',
    component: () => import('@/views/Permission.vue'),
  },
  {
    path: '/no-service',
    name: 'NoService',
    component: () => import('@/views/error/NoService.vue'),
  },
  {
    path: '/:pathMatch(.*)',
    name: '404',
    component: () => import('@/views/error/404.vue'),
  },
]
