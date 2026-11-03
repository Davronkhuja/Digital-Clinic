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
      { path: 'patients',     name: 'Patients',     component: () => import('@/views/PatientsView.vue') },
      { path: 'patients/:id', name: 'PatientProfile', component: () => import('@/views/PatientProfileView.vue') },
      { path: 'appointments', name: 'Appointments', component: () => import('@/views/AppointmentsView.vue') },
      { path: 'emr',          name: 'EMR',          component: () => import('@/views/EMRView.vue') },
      { path: 'finance',      name: 'Finance',      component: () => import('@/views/FinanceView.vue') },
      { path: 'analytics',    name: 'Analytics',    component: () => import('@/views/AnalyticsView.vue') },
      { path: 'ai',           name: 'AIAssistant',  component: () => import('@/views/AIAssistantView.vue') },
      { path: 'reports',      name: 'Reports',      component: () => import('@/views/ReportsView.vue') },
      { path: 'chat',         name: 'Chat',         component: () => import('@/views/ChatView.vue') },
      { path: 'staff',        name: 'Staff',        component: () => import('@/views/StaffView.vue') },
      { path: 'subscription', name: 'Subscription', component: () => import('@/views/SubscriptionView.vue') },
      { path: 'security',     name: 'Security',     component: () => import('@/views/SecurityView.vue') },
      { path: 'settings',     name: 'Settings',     component: () => import('@/views/SettingsView.vue') },
    ]
  },
  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFoundView.vue') }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isAuthenticated) return { name: 'Login' }
  if (to.meta.guest && auth.isAuthenticated) return { name: 'Dashboard' }
})

export default router