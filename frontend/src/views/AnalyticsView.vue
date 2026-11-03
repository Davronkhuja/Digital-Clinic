<template>
  <div class="space-y-5 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Tahlil</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Klinika faoliyati statistikasi va AI tahlili</p>
      </div>
      <div class="flex gap-2">
        <select v-model="period" class="input w-auto text-sm">
          <option value="week">Hafta</option>
          <option value="month">Oy</option>
          <option value="year">Yil</option>
          <option value="all">Hammasi</option>
        </select>
        <button @click="getAIInsight" :disabled="aiLoading || !loaded" class="btn-primary text-sm">
          <Bot class="w-4 h-4" />{{ aiLoading ? 'Tahlil qilinmoqda...' : 'AI Tahlil' }}
        </button>
      </div>
    </div>

    <div v-if="loading && !loaded" :class="['text-sm py-12 text-center', dark ? 'text-slate-400' : 'text-slate-500']">Yuklanmoqda...</div>
    <EmptyState v-else-if="error && !loaded" title="Ma'lumotni yuklab bo'lmadi" description="Server bilan aloqa o'rnatilmadi." action-label="Qayta urinish" @action="load" />

    <template v-else-if="loaded">
    <!-- KPI cards -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div v-for="kpi in kpiCards" :key="kpi.label" class="card p-5 relative overflow-hidden">
        <div :class="['absolute top-0 right-0 w-20 h-20 rounded-full -mr-6 -mt-6 opacity-10']"
          :style="`background:rgb(var(--c-primary))`"></div>
        <div class="flex items-start justify-between mb-3">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center" :class="kpi.bg">
            <component :is="kpi.icon" :class="['w-5 h-5', kpi.color]" />
          </div>
          <span v-if="kpi.hasChange && kpi.change != null && kpi.change !== 0" :class="['text-xs font-semibold px-1.5 py-0.5 rounded-lg', kpi.change > 0 ? 'text-emerald-500 bg-emerald-50 dark:bg-emerald-900/20' : 'text-red-500 bg-red-50 dark:bg-red-900/20']">
            {{ kpi.change > 0 ? '↑' : '↓' }}{{ Math.abs(kpi.change) }}%
          </span>
          <span v-else-if="kpi.hasChange" :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">—</span>
        </div>
        <p :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ kpi.value }}</p>
        <p :class="['text-xs mt-1', dark ? 'text-slate-400' : 'text-slate-500']">{{ kpi.label }}</p>
      </div>
    </div>

    <!-- Main charts grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">

      <!-- Top Diagnoses -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">🏥 Eng ko'p tashxislar</h3>
        <div class="space-y-3">
          <p v-if="!reports.top_diagnoses.length" class="text-sm text-slate-500">Ma'lumot yo'q</p>
          <div v-for="(d, i) in reports.top_diagnoses" :key="d.name" class="flex items-center gap-3">
            <span :class="['w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0']"
              :style="`background:rgba(var(--c-primary),${1 - i*0.15})`">{{ i+1 }}</span>
            <div class="flex-1">
              <div class="flex justify-between mb-1">
                <span :class="['text-sm font-medium', dark ? 'text-slate-200' : 'text-slate-800']">{{ d.name }}</span>
                <span :class="['text-xs', dark ? 'text-slate-400' : 'text-slate-500']">{{ d.count }} ta</span>
              </div>
              <div :class="['h-2 rounded-full overflow-hidden', dark ? 'bg-slate-800' : 'bg-slate-100']">
                <div class="h-full rounded-full transition-all duration-700"
                  :style="`width:${(d.count/reports.top_diagnoses[0].count)*100}%; background:rgba(var(--c-primary),${1-i*0.1})`"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Top Doctors -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">👨‍⚕️ Top shifokorlar</h3>
        <div class="space-y-3">
          <p v-if="!reports.top_doctors.length" class="text-sm text-slate-500">Ma'lumot yo'q</p>
          <div v-for="d in reports.top_doctors" :key="d.name"
            :class="['flex items-center justify-between p-3 rounded-xl border transition-colors', dark ? 'border-slate-800 hover:bg-slate-800/50' : 'border-slate-100 hover:bg-slate-50']">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold text-white shadow-sm"
                :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
                {{ d.name?.[0] || 'D' }}
              </div>
              <div>
                <p :class="['text-sm font-medium', dark ? 'text-slate-200' : 'text-slate-900']">{{ d.name }}</p>
                <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">{{ d.department }}</p>
              </div>
            </div>
            <div class="text-right">
              <p :class="['text-sm font-bold', dark ? 'text-white' : 'text-slate-900']">{{ d.patients }}</p>
              <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">bemor · {{ d.appointments }} qabul</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Monthly visits bar chart -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">📅 Oylik qabullar</h3>
        <p v-if="!monthlyData.length" class="text-sm text-slate-500">Ma'lumot yo'q</p>
        <div class="flex items-end gap-2 h-40">
          <div v-for="m in monthlyData" :key="m.month" class="flex-1 flex flex-col items-center gap-1 group">
            <span :class="['text-[10px] opacity-0 group-hover:opacity-100 transition-opacity font-semibold', dark ? 'text-slate-300' : 'text-slate-600']">{{ m.count }}</span>
            <div class="w-full rounded-t-lg transition-all duration-700 cursor-pointer hover:opacity-90"
              :style="`height:${maxMonthly ? (m.count/maxMonthly)*100 : 0}%; background:linear-gradient(to top,rgb(var(--c-primary)),rgb(var(--c-secondary)))`"></div>
            <span :class="['text-[10px]', dark ? 'text-slate-500' : 'text-slate-400']">{{ m.month }}</span>
          </div>
        </div>
      </div>

      <!-- Patient age distribution -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">👥 Yosh taqsimoti</h3>
        <div class="space-y-3">
          <p v-if="!ageGroups.length" class="text-sm text-slate-500">Ma'lumot yo'q</p>
          <div v-for="ag in ageGroups" :key="ag.label" class="flex items-center gap-3">
            <span :class="['text-xs w-16 flex-shrink-0', dark ? 'text-slate-400' : 'text-slate-500']">{{ ag.label }}</span>
            <div class="flex-1 flex items-center gap-2">
              <div :class="['h-3 rounded-full overflow-hidden flex-1', dark ? 'bg-slate-800' : 'bg-slate-100']">
                <div class="h-full rounded-full transition-all duration-700"
                  :style="`width:${ag.pct}%; background:rgba(var(--c-primary),${0.4+ag.pct/100*0.6})`"></div>
              </div>
              <span :class="['text-xs w-8 text-right font-medium', dark ? 'text-slate-300' : 'text-slate-600']">{{ ag.pct }}%</span>
            </div>
          </div>
        </div>

        <p v-if="demo.unknown_age" :class="['text-xs mt-3', dark ? 'text-slate-500' : 'text-slate-400']">Yoshi noma'lum: {{ demo.unknown_age }} ta</p>

        <!-- Departments -->
        <div class="mt-5 pt-4 border-t" :class="dark ? 'border-slate-800' : 'border-slate-100'">
          <h4 :class="['text-sm font-semibold mb-3', dark ? 'text-slate-300' : 'text-slate-700']">Bo'limlar bo'yicha qabullar</h4>
          <div class="space-y-2">
            <p v-if="!departments.length" class="text-sm text-slate-500">Ma'lumot yo'q</p>
            <div v-for="dep in departments" :key="dep.name" class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <div class="w-2.5 h-2.5 rounded-full" :style="`background:${dep.color}`"></div>
                <span :class="['text-xs', dark ? 'text-slate-400' : 'text-slate-600']">{{ dep.name }}</span>
              </div>
              <span :class="['text-xs font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">{{ dep.count }} ({{ dep.pct }}%)</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Appointment statuses -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">📋 Qabul statuslari</h3>
        <div class="space-y-2">
          <div v-for="s in statusRows" :key="s.key" class="flex items-center justify-between">
            <span :class="['text-sm', dark ? 'text-slate-400' : 'text-slate-600']">{{ s.label }}</span>
            <span :class="['text-sm font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">{{ s.count }}</span>
          </div>
        </div>
        <div class="mt-4 pt-4 border-t grid grid-cols-2 gap-3" :class="dark ? 'border-slate-800' : 'border-slate-100'">
          <div>
            <p :class="['text-xl font-bold', dark ? 'text-white' : 'text-slate-900']">{{ cancelRate }}</p>
            <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">Bekor qilish ulushi</p>
          </div>
          <div>
            <p :class="['text-xl font-bold', dark ? 'text-white' : 'text-slate-900']">{{ noShowRate }}</p>
            <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">Kelmay qolish ulushi</p>
          </div>
        </div>
      </div>

      <!-- Gender -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">⚧ Jins taqsimoti</h3>
        <div class="space-y-3">
          <div v-for="g in genderRows" :key="g.label" class="flex items-center gap-3">
            <span :class="['text-xs w-16 flex-shrink-0', dark ? 'text-slate-400' : 'text-slate-500']">{{ g.label }}</span>
            <div :class="['h-3 rounded-full overflow-hidden flex-1', dark ? 'bg-slate-800' : 'bg-slate-100']">
              <div class="h-full rounded-full transition-all duration-700" :style="`width:${g.pct}%; background:rgb(var(--c-primary))`"></div>
            </div>
            <span :class="['text-xs w-24 text-right font-medium', dark ? 'text-slate-300' : 'text-slate-600']">{{ g.count }} ({{ g.pct }}%)</span>
          </div>
        </div>
      </div>
    </div>
    </template>

    <!-- AI Insight Panel -->
    <Transition name="slide-down">
      <div v-if="aiInsight || aiLoading" :class="['card p-5 border-l-4', dark ? 'border-l-cyan-500' : 'border-l-cyan-500']" :style="`border-left-color:rgb(var(--c-primary))`">
        <div class="flex items-start gap-4">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 shadow"
            :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
            <Bot class="w-5 h-5 text-white" />
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-2">
              <p :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">AI Tahlil natijasi</p>
              <span class="text-[10px] px-2 py-0.5 rounded-full text-white font-semibold" :style="`background:rgb(var(--c-primary))`">{{ aiDemo ? 'Demo rejim' : 'AI' }}</span>
            </div>
            <div v-if="aiLoading" class="flex gap-1 items-center">
              <span class="w-2 h-2 rounded-full animate-bounce" :style="`background:rgb(var(--c-primary))`" style="animation-delay:0ms"></span>
              <span class="w-2 h-2 rounded-full animate-bounce" :style="`background:rgb(var(--c-primary))`" style="animation-delay:150ms"></span>
              <span class="w-2 h-2 rounded-full animate-bounce" :style="`background:rgb(var(--c-primary))`" style="animation-delay:300ms"></span>
              <span :class="['ml-2 text-sm', dark ? 'text-slate-400' : 'text-slate-500']">Statistika tahlil qilinmoqda...</span>
            </div>
            <p v-else :class="['text-sm leading-relaxed whitespace-pre-wrap', dark ? 'text-slate-300' : 'text-slate-600']">{{ aiInsight }}</p>
          </div>
          <button v-if="!aiLoading" @click="aiInsight = ''" :class="['p-1.5 rounded-lg flex-shrink-0', dark ? 'text-slate-500 hover:bg-slate-800' : 'text-slate-400 hover:bg-slate-100']">
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Users, Calendar, TrendingUp, Bot, X } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast  = useToast()
const theme  = useThemeStore()
const dark   = computed(() => theme.isDark)
const period = ref('month')

const MONTHS = ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyn', 'Iyl', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']
const PERIOD_LABELS = { week: 'hafta', month: 'oy', year: 'yil', all: 'barcha vaqt' }

const loading = ref(false)
const error = ref(false)
const dash = ref(null)
const reports = ref(null)
const loaded = computed(() => !!dash.value && !!reports.value)

const aiLoading = ref(false)
const aiInsight = ref('')
const aiDemo = ref(false)

function fmt(v) { return new Intl.NumberFormat('uz-UZ').format(v ?? 0) }
function pct(n, total) { return total ? Math.round((n / total) * 1000) / 10 : 0 }

async function load() {
  loading.value = true
  error.value = false
  try {
    const params = { period: period.value }
    const [d, r] = await Promise.all([
      api.get('/analytics/dashboard', { params }),
      api.get('/analytics/reports', { params }),
    ])
    dash.value = d.data
    reports.value = r.data
  } catch (e) {
    error.value = true
    toast.error(e, "Ma'lumotni yuklab bo'lmadi")
  } finally {
    loading.value = false
  }
}

watch(period, load)
onMounted(load)

const kpiCards = computed(() => {
  const d = dash.value || {}
  return [
    { label: 'Jami bemorlar', value: fmt(d.total_patients), icon: Users, bg: 'bg-blue-50 dark:bg-blue-900/20', color: 'text-blue-500' },
    { label: 'Davr qabullari', value: fmt(d.appointments), hasChange: true, change: d.changes?.appointments, icon: Calendar, bg: 'bg-violet-50 dark:bg-violet-900/20', color: 'text-violet-500' },
    { label: 'Daromad (UZS)', value: fmt(d.revenue), hasChange: true, change: d.changes?.revenue, icon: TrendingUp, bg: 'bg-emerald-50 dark:bg-emerald-900/20', color: 'text-emerald-500' },
  ]
})

const monthlyData = computed(() => (reports.value?.monthly_appointments || []).map(m => ({
  month: MONTHS[Number(String(m.month).split('-')[1]) - 1] || m.month,
  count: m.value,
})))
const maxMonthly = computed(() => Math.max(0, ...monthlyData.value.map(m => m.count)))

const demo = computed(() => reports.value?.patient_demographics || {})
const ageGroups = computed(() => (demo.value.age_groups || []).filter(a => a.count > 0 || a.pct > 0).length ? demo.value.age_groups : [])

const COLORS = ['rgb(var(--c-primary))', 'rgba(var(--c-secondary),.8)', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444']
const departments = computed(() => (reports.value?.departments || []).map((d, i) => ({ ...d, color: COLORS[i % COLORS.length] })))

const STATUS_LABELS = { Scheduled: 'Rejalashtirilgan', Completed: 'Yakunlangan', Cancelled: 'Bekor qilingan', 'No Show': 'Kelmay qolgan' }
const statusRows = computed(() => Object.entries(STATUS_LABELS).map(([key, label]) => ({
  key, label, count: reports.value?.appointment_statuses?.[key] || 0,
})))
const statusTotal = computed(() => statusRows.value.reduce((s, r) => s + r.count, 0))
const rate = key => statusTotal.value ? `${pct(reports.value?.appointment_statuses?.[key] || 0, statusTotal.value)}%` : '—'
const cancelRate = computed(() => rate('Cancelled'))
const noShowRate = computed(() => rate('No Show'))

const genderRows = computed(() => {
  const g = demo.value.gender || {}
  const total = (g.male || 0) + (g.female || 0) + (g.other || 0)
  return [
    { label: 'Erkak', count: g.male || 0 },
    { label: 'Ayol', count: g.female || 0 },
    { label: 'Boshqa', count: g.other || 0 },
  ].map(r => ({ ...r, pct: pct(r.count, total) }))
})

function buildStatsText() {
  const d = dash.value
  const r = reports.value
  const ch = v => (v == null ? "solishtirib bo'lmaydi" : `${v > 0 ? '+' : ''}${v}%`)
  const lines = [
    `Klinika statistikasi (${PERIOD_LABELS[period.value] || period.value}):`,
    `- Jami bemorlar: ${fmt(d.total_patients)}`,
    `- Yangi bemorlar: ${fmt(d.new_patients)} (${ch(d.changes?.new_patients)})`,
    `- Davr qabullari: ${fmt(d.appointments)} (${ch(d.changes?.appointments)})`,
    `- Bugungi qabullar: ${fmt(d.appointments_today)}`,
    `- Daromad: ${fmt(d.revenue)} UZS (${ch(d.changes?.revenue)})`,
    `- Xarajat: ${fmt(d.expense)} UZS`,
    `- Faol shifokorlar soni: ${fmt(d.active_doctors)}`,
  ]
  if (r.top_diagnoses.length) lines.push(`- Eng ko'p tashxislar: ${r.top_diagnoses.map(x => `${x.name} (${x.count})`).join(', ')}`)
  if (r.top_doctors.length) lines.push(`- Top shifokorlar: ${r.top_doctors.map(x => `${x.name}, ${x.department} (${x.patients} bemor, ${x.appointments} qabul)`).join('; ')}`)
  lines.push(`- Qabul statuslari: ${statusRows.value.map(s => `${s.label}: ${s.count}`).join(', ')}; bekor qilish ulushi ${cancelRate.value}, kelmay qolish ulushi ${noShowRate.value}`)
  if (r.departments.length) lines.push(`- Bo'limlar: ${r.departments.map(x => `${x.name}: ${x.count} (${x.pct}%)`).join(', ')}`)
  if (r.monthly_appointments.length) lines.push(`- Oylik qabullar: ${r.monthly_appointments.map(x => `${x.month}: ${x.value}`).join(', ')}`)
  if (ageGroups.value.length) lines.push(`- Yosh taqsimoti: ${ageGroups.value.map(x => `${x.label}: ${x.pct}%`).join(', ')}`)
  lines.push(`- Jins: ${genderRows.value.map(x => `${x.label}: ${x.count}`).join(', ')}`)
  return lines.join('\n')
}

async function getAIInsight() {
  if (!loaded.value) return
  aiLoading.value = true
  aiInsight.value = ''

  try {
    const { data } = await api.post('/ai/analyze', { period: period.value, stats: buildStatsText() })
    aiDemo.value = !!data.demo
    aiInsight.value = data.analysis || 'Tahlil natijasi olinmadi.'

  } catch (e) {
    console.error('Analytics AI error:', e)
    aiInsight.value = `⚠️ AI tahlili vaqtincha mavjud emas: ${e.response?.data?.detail || e.message}`
  } finally {
    aiLoading.value = false
  }
}
</script>

<style scoped>
.slide-down-enter-active { transition: all .3s ease-out; }
.slide-down-leave-active { transition: all .2s ease-in; }
.slide-down-enter-from   { opacity: 0; transform: translateY(-12px); }
.slide-down-leave-to     { opacity: 0; transform: translateY(-8px); }
</style>