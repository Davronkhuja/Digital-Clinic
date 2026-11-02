<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Xavfsizlik</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Monitor security and audit logs</p>
    </div>

    <!-- Top stat cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div v-for="s in statCards" :key="s.label" class="card p-5">
        <div class="flex items-start justify-between">
          <div :class="['w-10 h-10 rounded-xl flex items-center justify-center', s.iconBg]">
            <component :is="s.icon" :class="['w-5 h-5', s.iconColor]" />
          </div>
          <component :is="s.ok ? CheckCircle2 : AlertTriangle" :class="['w-5 h-5', s.ok ? 'text-emerald-500' : 'text-amber-500']" />
        </div>
        <p :class="['font-semibold mt-3', dark ? 'text-white' : 'text-slate-900']">{{ s.label }}</p>
        <p :class="['text-xs mt-0.5', dark ? 'text-slate-400' : 'text-slate-500']">{{ s.sub }}</p>
      </div>
    </div>

    <!-- Audit logs + Login activity -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">

      <!-- Audit Logs -->
      <div class="card p-5">
        <div class="flex items-center gap-2 mb-4">
          <ClipboardList :class="['w-4 h-4', dark ? 'text-slate-400' : 'text-slate-500']" />
          <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Audit Logs</h3>
        </div>
        <div class="space-y-1">
          <div v-for="log in auditLogs" :key="log.id"
            :class="['flex items-center justify-between p-3 rounded-xl transition-colors',
              dark ? 'hover:bg-slate-800' : 'hover:bg-slate-50']">
            <div>
              <p :class="['text-sm font-medium', dark ? 'text-slate-200' : 'text-slate-800']">{{ log.action }}</p>
              <p :class="['text-xs mt-0.5', dark ? 'text-slate-500' : 'text-slate-400']">
                {{ log.user }} • {{ log.ip }} • {{ log.time }}
              </p>
            </div>
            <span :class="[
              'badge text-xs',
              log.level === 'high'   ? 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400' :
              log.level === 'medium' ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/40 dark:text-amber-400' :
                                       'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400'
            ]">{{ log.level }}</span>
          </div>
        </div>
      </div>

      <!-- Login Activity -->
      <div class="card p-5">
        <div class="flex items-center gap-2 mb-4">
          <Monitor :class="['w-4 h-4', dark ? 'text-slate-400' : 'text-slate-500']" />
          <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Login Activity</h3>
        </div>
        <div class="space-y-1">
          <div v-for="session in loginSessions" :key="session.id"
            :class="['flex items-center justify-between p-3 rounded-xl transition-colors',
              dark ? 'hover:bg-slate-800' : 'hover:bg-slate-50']">
            <div class="flex items-center gap-3">
              <div :class="['w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0', dark ? 'bg-slate-800' : 'bg-slate-100']">
                <component :is="session.deviceIcon" :class="['w-4 h-4', dark ? 'text-slate-400' : 'text-slate-500']" />
              </div>
              <div>
                <p :class="['text-sm font-medium', dark ? 'text-slate-200' : 'text-slate-800']">{{ session.device }}</p>
                <p :class="['text-xs mt-0.5', dark ? 'text-slate-500' : 'text-slate-400']">{{ session.location }} • {{ session.time }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <span :class="[
                'badge text-xs',
                session.status === 'active'  ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400' :
                session.status === 'expired' ? 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400' :
                                               'bg-amber-100 text-amber-600'
              ]">{{ session.status }}</span>
              <button v-if="session.status !== 'expired'" @click="revokeSession(session.id)"
                :class="['p-1 rounded-lg transition-colors text-red-500', dark ? 'hover:bg-red-900/20' : 'hover:bg-red-50']">
                <X class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Password + Security status -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="card p-6">
        <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">Parolni o'zgartirish</h3>
        <form @submit.prevent="changePassword" class="space-y-4">
          <div>
            <label :class="lbl">Joriy parol</label>
            <input type="password" v-model="pwForm.current" class="input" placeholder="••••••••" />
          </div>
          <div>
            <label :class="lbl">Yangi parol</label>
            <input type="password" v-model="pwForm.newPw" class="input" placeholder="••••••••" />
            <!-- Strength bar -->
            <div v-if="pwForm.newPw" class="mt-2 flex gap-1">
              <div v-for="i in 4" :key="i" :class="['h-1 flex-1 rounded-full transition-all', i <= pwStrength ? strengthColor : dark ? 'bg-slate-700' : 'bg-slate-200']"></div>
            </div>
          </div>
          <div>
            <label :class="lbl">Tasdiqlang</label>
            <input type="password" v-model="pwForm.confirm" class="input" placeholder="••••••••" />
          </div>
          <div class="flex items-center justify-between">
            <Transition name="fade-q">
              <p v-if="pwSaved" class="text-emerald-500 text-sm flex items-center gap-1"><CheckCircle2 class="w-4 h-4" />Yangilandi!</p>
              <p v-else-if="pwError" class="text-red-500 text-sm">{{ pwError }}</p>
            </Transition>
            <button type="submit" class="btn-primary ml-auto"><Key class="w-4 h-4" />Yangilash</button>
          </div>
        </form>
      </div>

      <div class="card p-6">
        <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">Xavfsizlik holati</h3>
        <div class="space-y-2.5">
          <div v-for="item in securityItems" :key="item.label"
            :class="['flex items-center justify-between p-3 rounded-xl', dark ? 'bg-slate-800/50' : 'bg-slate-50']">
            <div class="flex items-center gap-3">
              <component :is="item.icon" :class="['w-4 h-4', item.ok ? 'text-emerald-500' : 'text-amber-500']" />
              <span :class="['text-sm', dark ? 'text-slate-300' : 'text-slate-700']">{{ item.label }}</span>
            </div>
            <span :class="item.ok ? 'badge-green' : 'badge-yellow'">{{ item.ok ? 'Yaxshi' : "Diqqat" }}</span>
          </div>
        </div>
        <div :class="['mt-4 p-4 rounded-xl', dark ? 'bg-slate-800' : 'bg-slate-900']">
          <p class="text-xs font-semibold text-cyan-400 mb-1">So'nggi kirish</p>
          <p class="text-sm text-white">2026-02-23 09:15 • Toshkent, UZ</p>
          <p class="text-xs text-slate-400 mt-0.5">Chrome 121 • Windows 11</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { Shield, Key, Smartphone, Bell, CheckCircle2, AlertTriangle, ClipboardList, Monitor, Laptop, X, Lock, Database } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
const dark = computed(() => theme.isDark)
const lbl = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])

const statCards = [
  { label: 'Encryption', sub: 'AES-256', icon: Lock, iconBg: 'bg-blue-50 dark:bg-blue-900/30', iconColor: 'text-blue-500', ok: true },
  { label: 'Backup', sub: 'Last: 2 hours ago', icon: Database, iconBg: 'bg-emerald-50 dark:bg-emerald-900/30', iconColor: 'text-emerald-500', ok: true },
  { label: 'Firewall', sub: 'Active', icon: Shield, iconBg: 'bg-cyan-50 dark:bg-cyan-900/30', iconColor: 'text-cyan-500', ok: true },
  { label: 'Threats', sub: '1 blocked today', icon: AlertTriangle, iconBg: 'bg-amber-50 dark:bg-amber-900/30', iconColor: 'text-amber-500', ok: false },
]

const auditLogs = ref([
  { id: 1, action: 'Changed user permissions', user: 'Admin', ip: '192.168.1.1', time: '5 min ago', level: 'low' },
  { id: 2, action: 'Exported patient data', user: 'Dr. Karimov', ip: '192.168.1.15', time: '1 hour ago', level: 'medium' },
  { id: 3, action: 'Updated billing settings', user: 'Admin', ip: '192.168.1.1', time: '3 hours ago', level: 'low' },
  { id: 4, action: 'Failed login attempt (3x)', user: 'Unknown', ip: '45.33.12.98', time: '6 hours ago', level: 'high' },
])

const loginSessions = ref([
  { id: 1, device: 'Chrome on Windows', location: 'Tashkent, UZ', time: 'Now', status: 'active', deviceIcon: Monitor },
  { id: 2, device: 'Safari on iPhone', location: 'Tashkent, UZ', time: '2 hours ago', status: 'active', deviceIcon: Smartphone },
  { id: 3, device: 'Firefox on macOS', location: 'Samarkand, UZ', time: '1 day ago', status: 'expired', deviceIcon: Laptop },
])

function revokeSession(id) {
  loginSessions.value = loginSessions.value.map(s => s.id === id ? { ...s, status: 'expired' } : s)
}

// Password
const pwSaved = ref(false), pwError = ref('')
const pwForm = reactive({ current: '', newPw: '', confirm: '' })
const pwStrength = computed(() => {
  const p = pwForm.newPw
  let s = 0
  if (p.length >= 6) s++
  if (p.length >= 10) s++
  if (/[A-Z]/.test(p) && /[0-9]/.test(p)) s++
  if (/[^A-Za-z0-9]/.test(p)) s++
  return s
})
const strengthColor = computed(() => {
  const colors = ['bg-red-500', 'bg-amber-500', 'bg-yellow-400', 'bg-emerald-500']
  return colors[pwStrength.value - 1] || 'bg-red-500'
})

function changePassword() {
  pwError.value = ''
  if (!pwForm.current) { pwError.value = 'Joriy parolni kiriting'; return }
  if (pwForm.newPw.length < 6) { pwError.value = 'Kamida 6 ta belgi'; return }
  if (pwForm.newPw !== pwForm.confirm) { pwError.value = 'Parollar mos kelmadi'; return }
  pwSaved.value = true
  Object.assign(pwForm, { current: '', newPw: '', confirm: '' })
  setTimeout(() => pwSaved.value = false, 2500)
}

const securityItems = [
  { label: 'Kuchli parol', icon: Key, ok: true },
  { label: 'Ikki bosqichli tekshiruv', icon: Smartphone, ok: false },
  { label: 'Xavfsiz ulanish (HTTPS)', icon: Shield, ok: true },
  { label: 'Kirish eslatmalari', icon: Bell, ok: true },
]
</script>

<style scoped>
.fade-q-enter-active { transition: opacity .2s; }
.fade-q-leave-active { transition: opacity .15s; }
.fade-q-enter-from, .fade-q-leave-to { opacity: 0; }
</style>