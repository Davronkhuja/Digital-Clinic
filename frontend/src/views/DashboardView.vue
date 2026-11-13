<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('page.dashboard') }}</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">{{ lang.t('dashboard.welcome') }}, {{ auth.user?.name || '' }}</p>
      </div>
      <select v-if="canView" v-model="period" class="input w-auto text-sm">
        <option v-for="p in periods" :key="p.value" :value="p.value">{{ p.label }}</option>
      </select>
    </div>

    <div v-if="!canView" :class="['rounded-2xl border p-6 text-sm', dark ? 'bg-slate-900 border-slate-800 text-slate-300' : 'bg-white border-slate-200 text-slate-600']">
      Chap menyudan kerakli bo'limni tanlang.
    </div>

    <div v-else-if="loading && !data" :class="['text-sm py-12 text-center', dark ? 'text-slate-400' : 'text-slate-500']">{{ lang.t('common.loading') }}</div>

    <EmptyState v-else-if="error && !data" title="Ma'lumotni yuklab bo'lmadi" description="Server bilan aloqa o'rnatilmadi." action-label="Qayta urinish" @action="load" />

    <template v-else-if="data">
      <!-- Stat cards -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="stat in stats" :key="stat.label" class="stat-card">
          <div class="flex items-start justify-between">
            <div>
              <p class="text-xs font-medium uppercase tracking-wide text-slate-500">{{ stat.label }}</p>
              <p :class="['text-2xl font-heading font-bold mt-1', dark ? 'text-white' : 'text-slate-900']">{{ stat.value }}</p>
              <p v-if="stat.hasChange" class="text-xs mt-1.5">
                <span v-if="stat.change == null" :class="dark ? 'text-slate-500' : 'text-slate-400'">—</span>
                <span v-else :class="stat.change > 0 ? 'text-emerald-500' : stat.change < 0 ? 'text-red-500' : (dark ? 'text-slate-400' : 'text-slate-500')" class="font-medium">{{ formatChange(stat.change) }}</span>
                <span :class="dark ? 'text-slate-500' : 'text-slate-400'" class="ml-1">oldingi davrga nisbatan</span>
              </p>
            </div>
            <div :class="['w-10 h-10 rounded-xl flex items-center justify-center', stat.bg]">
              <component :is="stat.icon" class="w-5 h-5" :class="stat.color" />
            </div>
          </div>
        </div>
      </div>

      <!-- Charts row -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div :class="['rounded-2xl border p-5', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
          <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('dashboard.monthly_revenue') }}</h3>
          <div class="h-52 flex items-end gap-2">
            <div v-for="item in revenueData" :key="item.month" class="flex-1 flex flex-col items-center gap-1">
              <div class="w-full rounded-t-lg bg-gradient-to-t from-cyan-500 to-blue-400 transition-all duration-700 hover:from-cyan-400 hover:to-blue-300"
                :style="{ height: `${maxRevenue ? (item.value / maxRevenue) * 180 : 0}px` }"
                :title="`${item.month}: ${formatMoney(item.value)}`">
              </div>
              <span class="text-xs text-slate-500">{{ item.month }}</span>
            </div>
          </div>
        </div>

        <div :class="['rounded-2xl border p-5', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
          <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('dashboard.patient_flow') }}</h3>
          <div class="h-40 flex items-end gap-3">
            <div v-for="d in patientFlow" :key="d.date" class="flex-1 flex flex-col items-center gap-1" :title="`${d.date}: ${d.new} + ${d.returning}`">
              <div class="w-full flex flex-col gap-0.5">
                <div class="w-full rounded-t bg-blue-400 opacity-60" :style="{ height: `${maxFlow ? (d.returning / maxFlow) * 110 : 0}px` }"></div>
                <div class="w-full rounded-t bg-cyan-500" :style="{ height: `${maxFlow ? (d.new / maxFlow) * 110 : 0}px` }"></div>
              </div>
              <span class="text-xs text-slate-500">{{ d.day }}</span>
            </div>
          </div>
          <div class="flex gap-4 mt-3">
            <span class="flex items-center gap-1.5 text-xs text-slate-500"><span class="w-3 h-2 rounded bg-cyan-500 inline-block"></span>{{ lang.t('dashboard.new') }}</span>
            <span class="flex items-center gap-1.5 text-xs text-slate-500"><span class="w-3 h-2 rounded bg-blue-400 opacity-60 inline-block"></span>{{ lang.t('dashboard.returning') }}</span>
          </div>
        </div>
      </div>
    </template>
    <NoShowCard v-if="canView" />
</div>
</template>

<script setup>
import NoShowCard from '@/components/NoShowCard.vue'
import { ref, computed, watch, onMounted } from 'vue'
import { DollarSign, Users, UserPlus, Calendar, CalendarCheck, Stethoscope } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useLanguageStore } from '@/stores/language'
import { useThemeStore } from '@/stores/theme'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast()
const auth = useAuthStore()
const lang = useLanguageStore()
const theme = useThemeStore()
const dark = computed(() => theme.isDark)

const periods = [
  { value: 'week', label: 'Hafta' },
  { value: 'month', label: 'Oy' },
  { value: 'year', label: 'Yil' },
  { value: 'all', label: 'Hammasi' },
]
const MONTHS = ['Yan', 'Fev', 'Mar', 'Apr', 'May', 'Iyn', 'Iyl', 'Avg', 'Sen', 'Okt', 'Noy', 'Dek']

const period = ref('month')
const data = ref(null)
const loading = ref(false)
const error = ref(false)
const canView = computed(() => auth.can('analytics:read'))

function formatMoney(v) { return new Intl.NumberFormat('uz-UZ').format(v ?? 0) }
function formatChange(v) { return `${v > 0 ? '+' : ''}${v}%` }
function monthName(ym) { return MONTHS[Number(String(ym).split('-')[1]) - 1] || ym }

const stats = computed(() => {
  const d = data.value
  if (!d) return []
  return [
    { label: 'Jami bemorlar', value: formatMoney(d.total_patients), icon: Users, bg: 'bg-blue-50 dark:bg-blue-900/20', color: 'text-blue-500' },
    { label: 'Yangi bemorlar', value: formatMoney(d.new_patients), hasChange: true, change: d.changes?.new_patients, icon: UserPlus, bg: 'bg-cyan-50 dark:bg-cyan-900/20', color: 'text-cyan-500' },
    { label: 'Bugungi qabullar', value: formatMoney(d.appointments_today), icon: CalendarCheck, bg: 'bg-amber-50 dark:bg-amber-900/20', color: 'text-amber-500' },
    { label: 'Davr qabullari', value: formatMoney(d.appointments), hasChange: true, change: d.changes?.appointments, icon: Calendar, bg: 'bg-violet-50 dark:bg-violet-900/20', color: 'text-violet-500' },
    { label: 'Daromad (UZS)', value: formatMoney(d.revenue), hasChange: true, change: d.changes?.revenue, icon: DollarSign, bg: 'bg-emerald-50 dark:bg-emerald-900/20', color: 'text-emerald-500' },
    { label: 'Faol shifokorlar', value: formatMoney(d.active_doctors), icon: Stethoscope, bg: 'bg-purple-50 dark:bg-purple-900/20', color: 'text-purple-500' },
  ]
})

const revenueData = computed(() => (data.value?.revenue_chart || []).map(r => ({ month: monthName(r.month), value: r.value })))
const maxRevenue = computed(() => Math.max(0, ...revenueData.value.map(d => d.value)))
const patientFlow = computed(() => data.value?.patient_flow || [])
const maxFlow = computed(() => Math.max(0, ...patientFlow.value.flatMap(d => [d.new, d.returning])))

async function load() {
  if (!canView.value) return
  loading.value = true
  error.value = false
  try {
    const { data: res } = await api.get('/analytics/dashboard', { params: { period: period.value } })
    data.value = res
  } catch (e) {
    error.value = true
    toast.error(e, "Ma'lumotni yuklab bo'lmadi")
  } finally {
    loading.value = false
  }
}

watch(period, load)
onMounted(load)
</script>
