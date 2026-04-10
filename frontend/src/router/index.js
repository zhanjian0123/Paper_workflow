import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '仪表盘' },
  },
  {
    path: '/papers',
    name: 'Papers',
    component: () => import('@/views/Papers.vue'),
    meta: { title: '论文库' },
  },
  {
    path: '/papers-list',
    redirect: '/papers',
  },
  {
    path: '/papers/upload',
    name: 'PaperUpload',
    component: () => import('@/views/PaperUpload.vue'),
    meta: { title: '论文上传' },
  },
  {
    path: '/workflows',
    name: 'Workflows',
    component: () => import('@/views/Workflows.vue'),
    meta: { title: '工作流列表' },
  },
  {
    path: '/workflows/:id',
    name: 'WorkflowDetail',
    component: () => import('@/views/WorkflowDetail.vue'),
    alias: '/workflow/:id',
    meta: { title: '工作流详情' },
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('@/views/Reports.vue'),
    meta: { title: '报告列表' },
  },
  {
    path: '/reports/:id',
    name: 'ReportDetail',
    component: () => import('@/views/ReportDetail.vue'),
    alias: '/report/:id',
    meta: { title: '报告详情' },
  },
  {
    path: '/memory',
    name: 'Memory',
    component: () => import('@/views/Memory.vue'),
    meta: { title: '记忆管理' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - 文献分析工作流系统`
  }
  next()
})

export default router
