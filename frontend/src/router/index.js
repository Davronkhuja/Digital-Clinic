import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  { path: '/login',           name: 'Login',          component: () => import('@/views/LoginView.vue'),          meta: { guest: true } },
  { path: '/forgot-password', name: 'ForgotPassword', component: () => import('@/views/ForgotPasswordView.vue'), meta: { guest: true } },

  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '',             name: 'Dashboard',    component: () => import('@/views/DashboardView.vue') },
      { path: 'patients',     name: 'Patients',     component: () => import('@/views/PatientsView.vue'), meta: { perm: 'patients:read' } },
      { path: 'patients/:id', name: 'PatientProfile', component: () => import('@/views/PatientProfileView.vue'), meta: { perm: 'patients:read' } },
      { path: 'appointments', name: 'Appointments', component: () => import('@/views/AppointmentsView.vue'), meta: { perm: 'appointments:read' } },
      { path: 'emr',          name: 'EMR',          component: () => import('@/views/EMRView.vue'), meta: { perm: 'emr:read' } },
      { path: 'lab',          name: 'Lab',          component: () => import('@/views/LabView.vue'), meta: { perm: 'lab:read' } },
      { path: 'finance',      name: 'Finance',      component: () => import('@/views/FinanceView.vue'), meta: { perm: 'finance:read' } },
      { path: 'analytics',    name: 'Analytics',    component: () => import('@/views/AnalyticsView.vue'), meta: { perm: 'analytics:read' } },
      { path: 'ai',           name: 'AIAssistant',  component: () => import('@/views/AIAssistantView.vue'), meta: { perm: 'ai:use' } },
      { path: 'reports',      name: 'Reports',      component: () => import('@/views/ReportsView.vue'), meta: { perm: 'reports:read' } },
      { path: 'chat',         name: 'Chat',         component: () => import('@/views/ChatView.vue'), meta: { hidden: true } },
      { path: 'staff',        name: 'Staff',        component: () => import('@/views/StaffView.vue'), meta: { perm: 'staff:read' } },
      { path: 'subscription', name: 'Subscription', component: () => import('@/views/SubscriptionView.vue'), meta: { hidden: true } },
      { path: 'security',     name: 'Security',     component: () => import('@/views/SecurityView.vue'), meta: { perm: 'audit:read' } },
      { path: 'settings',     name: 'Settings',     component: () => import('@/views/SettingsView.vue'), meta: { perm: 'settings:read' } },
    ]
  },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFoundView.vue') }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

const firstAllowed = [
  ['/patients', 'patients:read'], ['/appointments', 'appointments:read'], ['/emr', 'emr:read'], ['/lab', 'lab:read'],
  ['/finance', 'finance:read'], ['/analytics', 'analytics:read'], ['/ai', 'ai:use'],
  ['/reports', 'reports:read'], ['/staff', 'staff:read'], ['/security', 'audit:read'],
  ['/settings', 'settings:read'],
]

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) return { name: 'Login' }
  if (to.meta.guest && auth.isAuthenticated) return { name: 'Dashboard' }
  // Menyudan yashirilgan (hozircha ishlatilmaydigan) sahifalarga URL orqali ham kirib bo'lmaydi
  if (to.meta.hidden) return '/'
  if (auth.isAuthenticated) {
    await auth.fetchMe()
    const perm = to.meta.perm
    if (perm && !auth.can(perm)) {
      const target = firstAllowed.find(([, p]) => auth.can(p))
      return target ? target[0] : '/'
    }
  }
})

export default router
