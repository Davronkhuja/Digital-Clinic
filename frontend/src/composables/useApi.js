import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

function clearSession() {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user')
}

function redirectToLogin() {
  clearSession()
  if (window.location.pathname !== '/login') window.location.href = '/login'
}

// Bir vaqtda kelgan bir nechta 401 uchun bitta refresh so'rovi
let refreshing = null

function refreshTokens() {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return Promise.reject(new Error('no refresh token'))
  if (!refreshing) {
    // interceptor'siz toza axios: refresh o'zi 401 bersa sikl bo'lmasin
    refreshing = axios
      .post('/api/auth/refresh', { refresh_token: refreshToken })
      .then(({ data }) => {
        localStorage.setItem('token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        return data.access_token
      })
      .finally(() => { refreshing = null })
  }
  return refreshing
}

api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config
    const isAuthCall = original?.url?.startsWith('/auth/')
    if (err.response?.status !== 401 || !original || original._retried || isAuthCall) {
      // login/register 401 — oddiy xato (noto'g'ri parol), yo'naltirish kerak emas
      if (err.response?.status === 401 && !isAuthCall) redirectToLogin()
      return Promise.reject(err)
    }
    original._retried = true
    try {
      const token = await refreshTokens()
      original.headers.Authorization = `Bearer ${token}`
      return api(original)
    } catch {
      redirectToLogin()
      return Promise.reject(err)
    }
  }
)

// Backend `limit` ni 100 bilan cheklaydi: sahifalab hammasini yig'adi
export async function fetchAll(url, params = {}, pageSize = 100) {
  const items = []
  for (let skip = 0; ; skip += pageSize) {
    const { data } = await api.get(url, { params: { ...params, skip, limit: pageSize } })
    items.push(...data)
    if (data.length < pageSize) return items
  }
}

export default api
