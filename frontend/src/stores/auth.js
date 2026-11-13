import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/composables/useApi'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const token = ref(localStorage.getItem('token') || null)

  const isAuthenticated = computed(() => !!token.value)

  async function login(email, password) {
    const { data } = await api.post('/auth/login', { email, password })
    meLoaded = false
    token.value = data.access_token
    user.value = data.user
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    localStorage.setItem('user', JSON.stringify(data.user))
    return data
  }

  function can(perm) {
    return !!user.value?.permissions?.includes(perm)
  }

  // Rol/ruxsatlar o'zgargan bo'lishi mumkin: serverdan yangilaymiz (401 ni useApi hal qiladi)
  let meLoaded = false
  async function fetchMe(force = false) {
    if (!token.value || (meLoaded && !force)) return
    try {
      const { data } = await api.get('/auth/me')
      user.value = data
      localStorage.setItem('user', JSON.stringify(data))
      meLoaded = true
    } catch (e) {
      console.error('GET /auth/me xatosi', e)
    }
  }

  async function logout() {
    const refreshToken = localStorage.getItem('refresh_token')
    try {
      if (token.value) await api.post('/auth/logout', { refresh_token: refreshToken })
    } catch (e) {
      console.error('Logout so\'rovi xatosi', e)
    }
    meLoaded = false
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    localStorage.removeItem('branch_id')
  }

  return { user, token, isAuthenticated, login, logout, can, fetchMe }
})
