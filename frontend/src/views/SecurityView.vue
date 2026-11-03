<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Xavfsizlik</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Audit jurnali, sessiyalar va parol</p>
    </div>

    <!-- Audit jurnali -->
    <div v-if="canAudit" class="card p-5">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div class="flex items-center gap-2">
          <ClipboardList :class="['w-4 h-4', sub]" />
          <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Audit jurnali</h3>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <select v-model="auditFilter.action" class="input !w-auto text-sm" @change="auditFilterChanged">
            <option value="">Barcha amallar</option>
            <option v-for="(label, key) in ACTIONS" :key="key" :value="key">{{ label }}</option>
          </select>
          <select v-model="auditFilter.entity_type" class="input !w-auto text-sm" @change="auditFilterChanged">
            <option value="">Barcha obyektlar</option>
            <option v-for="(label, key) in ENTITIES" :key="key" :value="key">{{ label }}</option>
          </select>
          <button class="btn-secondary text-sm" :disabled="auditLoading" @click="loadAudit">
            <RefreshCw :class="['w-4 h-4', auditLoading && 'animate-spin']" />Yangilash
          </button>
        </div>
      </div>

      <div v-if="auditLoading && !audit.items.length" :class="['text-sm py-10 text-center', sub]">Yuklanmoqda...</div>
      <EmptyState v-else-if="auditError" title="Audit jurnalini yuklab bo'lmadi"
        description="Serverga ulanishda xatolik yuz berdi." action-label="Qayta urinish" @action="loadAudit" />
      <EmptyState v-else-if="!audit.items.length" title="Yozuvlar topilmadi"
        description="Tanlangan filtrlar bo'yicha audit yozuvlari yo'q." />
      <template v-else>
        <div class="table-container rounded-none border-0">
          <table class="table">
            <thead>
              <tr>
                <th>Vaqt</th><th>Foydalanuvchi</th><th>Amal</th><th>Obyekt turi</th>
                <th>Obyekt ID</th><th>IP</th><th>Tafsilot</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in audit.items" :key="log.id">
                <td class="whitespace-nowrap">{{ fmtDate(log.created_at) }}</td>
                <td>{{ auditUser(log) }}</td>
                <td>
                  <span :class="['badge text-xs', actionBadge(log.action)]">{{ ACTIONS[log.action] || log.action }}</span>
                </td>
                <td>{{ ENTITIES[log.entity_type] || log.entity_type || '—' }}</td>
                <td class="font-mono text-xs" :title="log.entity_id || ''">{{ shortId(log.entity_id) }}</td>
                <td class="whitespace-nowrap">{{ log.ip || '—' }}</td>
                <td class="text-xs max-w-[240px] truncate" :title="detailsText(log.details)">{{ detailsText(log.details) || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="flex items-center justify-between mt-4">
          <p :class="['text-xs', sub]">{{ auditFrom }}–{{ auditTo }} / {{ audit.total }}</p>
          <div class="flex gap-2">
            <button class="btn-secondary text-sm" :disabled="auditPage === 0 || auditLoading" @click="auditPage--; loadAudit()">Oldingi</button>
            <button class="btn-secondary text-sm" :disabled="auditTo >= audit.total || auditLoading" @click="auditPage++; loadAudit()">Keyingi</button>
          </div>
        </div>
      </template>
    </div>

    <!-- Barcha faol sessiyalar (administrator) -->
    <div v-if="canAudit" class="card p-5">
      <div class="flex items-center gap-2 mb-4">
        <Users :class="['w-4 h-4', sub]" />
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Faol sessiyalar (barcha foydalanuvchilar)</h3>
      </div>
      <div v-if="allLoading" :class="['text-sm py-8 text-center', sub]">Yuklanmoqda...</div>
      <EmptyState v-else-if="allError" title="Sessiyalarni yuklab bo'lmadi"
        description="Serverga ulanishda xatolik yuz berdi." action-label="Qayta urinish" @action="loadAll" />
      <EmptyState v-else-if="!allSessions.length" title="Faol sessiyalar yo'q" />
      <div v-else class="space-y-1">
        <div v-for="s in allSessions" :key="s.id"
          :class="['flex items-center justify-between gap-3 p-3 rounded-xl transition-colors',
            dark ? 'hover:bg-slate-800' : 'hover:bg-slate-50']">
          <div class="flex items-center gap-3 min-w-0">
            <div :class="['w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0', dark ? 'bg-slate-800' : 'bg-slate-100']">
              <Monitor :class="['w-4 h-4', sub]" />
            </div>
            <div class="min-w-0">
              <p :class="['text-sm font-medium truncate', dark ? 'text-slate-200' : 'text-slate-800']">
                {{ s.user_name || '—' }} <span :class="['text-xs font-normal', sub]">{{ s.email }}</span>
              </p>
              <p :class="['text-xs mt-0.5', dark ? 'text-slate-500' : 'text-slate-400']">
                {{ parseUA(s.user_agent) }} • {{ s.ip || '—' }} • {{ fmtDate(s.last_active) }}
              </p>
            </div>
          </div>
          <button v-if="canRevokeAll" @click="revoke(s, true)" title="Bekor qilish"
            :class="['p-1.5 rounded-lg transition-colors text-red-500', dark ? 'hover:bg-red-900/20' : 'hover:bg-red-50']">
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- Mening sessiyalarim -->
      <div class="card p-5">
        <div class="flex items-center gap-2 mb-4">
          <Monitor :class="['w-4 h-4', sub]" />
          <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Mening sessiyalarim</h3>
        </div>
        <div v-if="myLoading" :class="['text-sm py-8 text-center', sub]">Yuklanmoqda...</div>
        <EmptyState v-else-if="myError" title="Sessiyalarni yuklab bo'lmadi"
          description="Serverga ulanishda xatolik yuz berdi." action-label="Qayta urinish" @action="loadMy" />
        <EmptyState v-else-if="!mySessions.length" title="Faol sessiyalar yo'q" />
        <div v-else class="space-y-1">
          <div v-for="s in mySessions" :key="s.id"
            :class="['flex items-center justify-between gap-3 p-3 rounded-xl transition-colors',
              dark ? 'hover:bg-slate-800' : 'hover:bg-slate-50']">
            <div class="flex items-center gap-3 min-w-0">
              <div :class="['w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0', dark ? 'bg-slate-800' : 'bg-slate-100']">
                <Monitor :class="['w-4 h-4', sub]" />
              </div>
              <div class="min-w-0">
                <p :class="['text-sm font-medium truncate', dark ? 'text-slate-200' : 'text-slate-800']">{{ parseUA(s.user_agent) }}</p>
                <p :class="['text-xs mt-0.5', dark ? 'text-slate-500' : 'text-slate-400']">
                  {{ s.ip || '—' }} • {{ fmtDate(s.last_active) }}
                </p>
              </div>
            </div>
            <button @click="revoke(s, false)" title="Bekor qilish"
              :class="['p-1.5 rounded-lg transition-colors text-red-500', dark ? 'hover:bg-red-900/20' : 'hover:bg-red-50']">
              <X class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <!-- Parol -->
      <div class="card p-6">
        <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">Parolni o'zgartirish</h3>
        <form @submit.prevent="changePassword" class="space-y-4">
          <div>
            <label :class="lbl">Joriy parol</label>
            <input type="password" v-model="pwForm.current" class="input" placeholder="••••••••" autocomplete="current-password" />
          </div>
          <div>
            <label :class="lbl">Yangi parol</label>
            <input type="password" v-model="pwForm.newPw" class="input" placeholder="••••••••" autocomplete="new-password" />
            <div v-if="pwForm.newPw" class="mt-2 flex gap-1">
              <div v-for="i in 4" :key="i" :class="['h-1 flex-1 rounded-full transition-all', i <= pwStrength ? strengthColor : dark ? 'bg-slate-700' : 'bg-slate-200']"></div>
            </div>
          </div>
          <div>
            <label :class="lbl">Tasdiqlang</label>
            <input type="password" v-model="pwForm.confirm" class="input" placeholder="••••••••" autocomplete="new-password" />
          </div>
          <div class="flex items-center justify-between gap-3">
            <p v-if="pwError" class="text-red-500 text-sm">{{ pwError }}</p>
            <button type="submit" class="btn-primary ml-auto" :disabled="pwSaving">
              <Key class="w-4 h-4" />{{ pwSaving ? 'Saqlanmoqda...' : 'Yangilash' }}
            </button>
          </div>
          <p :class="['text-xs', sub]">Parol o'zgargach barcha qurilmalardan chiqarilasiz va qayta kirishingiz kerak bo'ladi.</p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Key, ClipboardList, Monitor, X, Users, RefreshCw } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/ui/EmptyState.vue'

const theme = useThemeStore()
const auth = useAuthStore()
const toast = useToast()
const router = useRouter()

const dark = computed(() => theme.isDark)
const lbl = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])
const sub = computed(() => dark.value ? 'text-slate-400' : 'text-slate-500')

const canAudit = computed(() => auth.can('audit:read'))
const canRevokeAll = computed(() => auth.can('roles:manage'))

const ACTIONS = {
  read: "o'qildi",
  create: 'yaratildi',
  update: "o'zgartirildi",
  delete: "o'chirildi",
  login: 'kirdi',
  login_failed: 'kirish urinishi muvaffaqiyatsiz',
  logout: 'chiqdi',
  change_password: "parol o'zgartirildi",
  revoke_session: 'sessiya bekor qilindi',
}
const ENTITIES = {
  patient: 'Bemor', emr: 'Tibbiy karta', transaction: 'Tranzaksiya', auth: 'Autentifikatsiya',
  user: 'Foydalanuvchi', role: 'Rol', session: 'Sessiya', report: 'Hisobot',
}

function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return isNaN(d) ? '—' : d.toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' })
}
function shortId(id) {
  if (!id) return '—'
  return id.length > 8 ? id.slice(0, 8) + '…' : id
}
function detailsText(d) {
  if (!d) return ''
  return Object.entries(d).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join(', ')
}
function auditUser(log) {
  return log.user_name || (log.action === 'login_failed' && log.details?.email) || '—'
}
function actionBadge(a) {
  if (a === 'login_failed' || a === 'delete' || a === 'revoke_session') return 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400'
  if (a === 'update' || a === 'change_password') return 'bg-amber-100 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400'
  if (a === 'create' || a === 'login') return 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400'
  return 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400'
}
function parseUA(ua) {
  if (!ua) return "Noma'lum qurilma"
  const browser =
    /Edg\//.test(ua) ? 'Edge' :
    /OPR\/|Opera/.test(ua) ? 'Opera' :
    /Firefox\//.test(ua) ? 'Firefox' :
    /Chrome\//.test(ua) ? 'Chrome' :
    /Safari\//.test(ua) ? 'Safari' :
    /python|axios|curl/i.test(ua) ? ua.split('/')[0] : 'Brauzer'
  const os =
    /Windows/.test(ua) ? 'Windows' :
    /Android/.test(ua) ? 'Android' :
    /iPhone|iPad|iOS/.test(ua) ? 'iOS' :
    /Mac OS X|Macintosh/.test(ua) ? 'macOS' :
    /Linux/.test(ua) ? 'Linux' : ''
  return os ? `${browser} • ${os}` : browser
}

// Audit
const PAGE = 20
const audit = reactive({ items: [], total: 0 })
const auditFilter = reactive({ action: '', entity_type: '' })
const auditPage = ref(0)
const auditLoading = ref(false)
const auditError = ref(false)
const auditFrom = computed(() => audit.total ? auditPage.value * PAGE + 1 : 0)
const auditTo = computed(() => Math.min((auditPage.value + 1) * PAGE, audit.total))

async function loadAudit() {
  auditLoading.value = true
  auditError.value = false
  try {
    const params = { skip: auditPage.value * PAGE, limit: PAGE }
    if (auditFilter.action) params.action = auditFilter.action
    if (auditFilter.entity_type) params.entity_type = auditFilter.entity_type
    const { data } = await api.get('/security/audit', { params })
    audit.items = data.items || []
    audit.total = data.total || 0
  } catch (e) {
    auditError.value = true
    toast.error(e, "Audit jurnalini yuklab bo'lmadi")
  } finally {
    auditLoading.value = false
  }
}
function auditFilterChanged() { auditPage.value = 0; loadAudit() }

// Sessiyalar
const mySessions = ref([])
const myLoading = ref(false)
const myError = ref(false)
const allSessions = ref([])
const allLoading = ref(false)
const allError = ref(false)

async function loadMy() {
  myLoading.value = true
  myError.value = false
  try {
    const { data } = await api.get('/auth/sessions')
    mySessions.value = data
  } catch (e) {
    myError.value = true
    toast.error(e, "Sessiyalarni yuklab bo'lmadi")
  } finally {
    myLoading.value = false
  }
}
async function loadAll() {
  allLoading.value = true
  allError.value = false
  try {
    const { data } = await api.get('/security/sessions')
    allSessions.value = data
  } catch (e) {
    allError.value = true
    toast.error(e, "Sessiyalarni yuklab bo'lmadi")
  } finally {
    allLoading.value = false
  }
}

async function revoke(s, admin) {
  if (!window.confirm("Sessiyani bekor qilasizmi?\n\nRefresh token bekor qilinadi; joriy access token 30 daqiqagacha ishlashi mumkin.")) return
  try {
    await api.delete(`${admin ? '/security/sessions' : '/auth/sessions'}/${s.id}`)
    toast.success('Sessiya bekor qilindi')
    await Promise.all([loadMy(), canAudit.value ? loadAll() : null, canAudit.value ? loadAudit() : null])
  } catch (e) {
    toast.error(e, "Sessiyani bekor qilib bo'lmadi")
  }
}

// Parol
const pwSaving = ref(false), pwError = ref('')
const pwForm = reactive({ current: '', newPw: '', confirm: '' })
const pwStrength = computed(() => {
  const p = pwForm.newPw
  let s = 0
  if (p.length >= 8) s++
  if (p.length >= 12) s++
  if (/[A-Z]/.test(p) && /[0-9]/.test(p)) s++
  if (/[^A-Za-z0-9]/.test(p)) s++
  return s
})
const strengthColor = computed(() => {
  const colors = ['bg-red-500', 'bg-amber-500', 'bg-yellow-400', 'bg-emerald-500']
  return colors[pwStrength.value - 1] || 'bg-red-500'
})

async function changePassword() {
  pwError.value = ''
  if (!pwForm.current) { pwError.value = 'Joriy parolni kiriting'; return }
  if (pwForm.newPw.length < 8) { pwError.value = 'Kamida 8 ta belgi'; return }
  if (pwForm.newPw.length > 72) { pwError.value = "Ko'pi bilan 72 ta belgi"; return }
  if (pwForm.newPw !== pwForm.confirm) { pwError.value = 'Parollar mos kelmadi'; return }
  pwSaving.value = true
  try {
    await api.post('/auth/change-password', { current_password: pwForm.current, new_password: pwForm.newPw })
    toast.success("Parol yangilandi. Barcha qurilmalardan chiqarildingiz, qayta kiring")
    Object.assign(pwForm, { current: '', newPw: '', confirm: '' })
    auth.logout()
    router.push('/login')
  } catch (e) {
    toast.error(e, "Parolni o'zgartirib bo'lmadi")
  } finally {
    pwSaving.value = false
  }
}

onMounted(() => {
  loadMy()
  if (canAudit.value) { loadAudit(); loadAll() }
})
</script>
