import { reactive } from 'vue'

export const toasts = reactive([])
let nextId = 1

function push(type, message, timeout = 4500) {
  const id = nextId++
  toasts.push({ id, type, message })
  setTimeout(() => dismiss(id), timeout)
}

export function dismiss(id) {
  const i = toasts.findIndex(t => t.id === id)
  if (i >= 0) toasts.splice(i, 1)
}

// FastAPI xatosi: {detail: "..."} yoki 422 uchun [{loc, msg}, ...]
export function errorMessage(e, fallback = 'Xatolik yuz berdi') {
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map(d => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ')
  }
  if (e?.response) return `${fallback} (HTTP ${e.response.status})`
  return "Serverga ulanib bo'lmadi"
}

export function useToast() {
  return {
    success: msg => push('success', msg),
    error: (e, fallback) => push('error', typeof e === 'string' ? e : errorMessage(e, fallback), 7000),
    info: msg => push('info', msg),
  }
}
