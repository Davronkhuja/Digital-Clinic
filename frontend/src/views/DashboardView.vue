<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('page.dashboard') }}</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">{{ lang.t('dashboard.welcome') }}, {{ auth.user?.name || 'Admin' }} 👋</p>
    </div>

    <!-- Stat cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div v-for="stat in stats" :key="stat.key" class="stat-card">
        <div class="flex items-start justify-between">
          <div>
            <p :class="['text-xs font-medium uppercase tracking-wide', dark ? 'text-slate-500' : 'text-slate-500']">{{ lang.t(stat.key) }}</p>
            <p :class="['text-2xl font-heading font-bold mt-1', dark ? 'text-white' : 'text-slate-900']">{{ stat.value }}</p>
            <p class="text-xs mt-1.5">
              <span :class="stat.trend === 'up' ? 'text-emerald-500' : 'text-red-500'" class="font-medium">{{ stat.change }}</span>
              <span :class="dark ? 'text-slate-500' : 'text-slate-400'" class="ml-1">{{ lang.t('dashboard.vs_last_week') }}</span>
            </p>
          </div>
          <div :class="['w-10 h-10 rounded-xl flex items-center justify-center', stat.bg]">
            <component :is="stat.icon" class="w-5 h-5" :class="stat.color" />
          </div>
        </div>
      </div>
    </div>

    <!-- Charts row -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- Revenue bar chart -->
      <div :class="['lg:col-span-2 rounded-2xl border p-5', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
        <div class="flex items-center justify-between mb-4">
          <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('dashboard.monthly_revenue') }}</h3>
          <span class="badge badge-blue">2026</span>
        </div>
        <div class="h-52 flex items-end gap-2">
          <div v-for="item in revenueData" :key="item.month" class="flex-1 flex flex-col items-center gap-1">
            <div class="w-full rounded-t-lg bg-gradient-to-t from-cyan-500 to-blue-400 transition-all duration-700 hover:from-cyan-400 hover:to-blue-300"
              :style="{ height: `${(item.value / maxRevenue) * 180}px` }"
              :title="`${item.month}: ${formatMoney(item.value)}`">
            </div>
            <span :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-500']">{{ item.month }}</span>
          </div>
        </div>
      </div>

      <!-- AI Insights -->
      <div class="rounded-2xl border p-5 bg-gradient-to-br from-slate-900 to-slate-800 border-slate-700">
        <div class="flex items-center gap-2 mb-4">
          <Bot class="w-5 h-5 text-cyan-400" />
          <h3 class="font-heading font-semibold text-white">{{ lang.t('dashboard.ai_insights') }}</h3>
        </div>
        <div class="space-y-3">
          <div v-for="insight in aiInsights" :key="insight.key" class="p-3 rounded-xl border" :class="insight.cls">
            <p class="text-xs font-semibold" :class="insight.titleCls">{{ lang.t(insight.key) }}</p>
            <p class="text-xs text-slate-400 mt-0.5">{{ lang.t(insight.msgKey) }}</p>
          </div>
        </div>
        <RouterLink to="/ai" class="btn-primary w-full justify-center mt-4 text-xs">
          {{ lang.t('dashboard.ai_chat_btn') }}
        </RouterLink>
      </div>
    </div>

    <!-- Bottom row -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <!-- Patient flow -->
      <div :class="['rounded-2xl border p-5', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
        <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('dashboard.patient_flow') }}</h3>
        <div class="h-40 flex items-end gap-3">
          <div v-for="d in patientFlow" :key="d.day" class="flex-1 flex flex-col items-center gap-1">
            <div class="w-full flex flex-col gap-0.5">
              <div class="w-full rounded-t bg-blue-400 opacity-60" :style="{ height: `${d.returning * 1.2}px` }"></div>
              <div class="w-full rounded-t bg-cyan-500" :style="{ height: `${d.new * 2}px` }"></div>
            </div>
            <span :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-500']">{{ d.day }}</span>
          </div>
        </div>
        <div class="flex gap-4 mt-3">
          <span class="flex items-center gap-1.5 text-xs text-slate-500"><span class="w-3 h-2 rounded bg-cyan-500 inline-block"></span>{{ lang.t('dashboard.new') }}</span>
          <span class="flex items-center gap-1.5 text-xs text-slate-500"><span class="w-3 h-2 rounded bg-blue-400 opacity-60 inline-block"></span>{{ lang.t('dashboard.returning') }}</span>
        </div>
      </div>

      <!-- Recent activity -->
      <div :class="['rounded-2xl border p-5', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
        <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('dashboard.recent_activity') }}</h3>
        <div class="space-y-3">
          <div v-for="act in recentActivity" :key="act.name" class="flex items-center gap-3">
            <div :class="['w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0', act.bg, act.tc]">
              {{ act.name[0] }}
            </div>
            <div class="min-w-0 flex-1">
              <p :class="['text-sm font-medium truncate', dark ? 'text-slate-200' : 'text-slate-900']">{{ act.name }}</p>
              <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-500']">{{ act.desc }}</p>
            </div>
            <span :class="['text-xs flex-shrink-0', dark ? 'text-slate-600' : 'text-slate-400']">{{ act.time }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { DollarSign, Users, Calendar, Stethoscope, Bot } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useLanguageStore } from '@/stores/language'
import { useThemeStore } from '@/stores/theme'
import api from '@/composables/useApi'

const auth = useAuthStore()
const lang = useLanguageStore()
const theme = useThemeStore()
const dark = computed(() => theme.isDark)

const stats = [
  { key: 'dashboard.revenue', value: '48,250,000', change: '+12.5%', trend: 'up', icon: DollarSign, bg: 'bg-emerald-50 dark:bg-emerald-900/20', color: 'text-emerald-500' },
  { key: 'dashboard.patients', value: '1,284', change: '+3.2%', trend: 'up', icon: Users, bg: 'bg-blue-50 dark:bg-blue-900/20', color: 'text-blue-500' },
  { key: 'dashboard.appointments', value: '42', change: '-5.1%', trend: 'down', icon: Calendar, bg: 'bg-amber-50 dark:bg-amber-900/20', color: 'text-amber-500' },
  { key: 'dashboard.doctors', value: '18', change: '+2', trend: 'up', icon: Stethoscope, bg: 'bg-purple-50 dark:bg-purple-900/20', color: 'text-purple-500' },
]

const revenueData = ref([
  { month: 'Sep', value: 35000000 }, { month: 'Okt', value: 42000000 },
  { month: 'Noy', value: 38000000 }, { month: 'Dek', value: 45000000 },
  { month: 'Yan', value: 41000000 }, { month: 'Feb', value: 48250000 },
])
const maxRevenue = computed(() => Math.max(...revenueData.value.map(d => d.value)))

const patientFlow = ref([
  { day: 'Du', new: 12, returning: 28 }, { day: 'Se', new: 8, returning: 32 },
  { day: 'Ch', new: 15, returning: 25 }, { day: 'Pa', new: 10, returning: 30 },
  { day: 'Ju', new: 18, returning: 22 },
])

const aiInsights = [
  { key: 'dashboard.insight_cancel', msgKey: 'dashboard.insight_cancel_msg', cls: 'border-amber-500/20 bg-amber-500/10', titleCls: 'text-amber-400' },
  { key: 'dashboard.insight_revenue', msgKey: 'dashboard.insight_revenue_msg', cls: 'border-emerald-500/20 bg-emerald-500/10', titleCls: 'text-emerald-400' },
  { key: 'dashboard.insight_popular', msgKey: 'dashboard.insight_popular_msg', cls: 'border-cyan-500/20 bg-cyan-500/10', titleCls: 'text-cyan-400' },
]

const recentActivity = [
  { name: 'Aziza Karimova', desc: "Yangi bemor qo'shildi", time: '5 daq', bg: 'bg-blue-100', tc: 'text-blue-600' },
  { name: 'Dr. Rustamov', desc: 'Uchrashuv yakunlandi', time: '12 daq', bg: 'bg-emerald-100', tc: 'text-emerald-600' },
  { name: 'Bobur Aliyev', desc: 'EMR yangilandi', time: '25 daq', bg: 'bg-purple-100', tc: 'text-purple-600' },
  { name: 'Feruza Umarova', desc: "To'lov amalga oshirildi", time: '1 soat', bg: 'bg-amber-100', tc: 'text-amber-600' },
]

function formatMoney(v) { return new Intl.NumberFormat('uz-UZ').format(v) }

onMounted(async () => {
  try {
    const { data } = await api.get('/analytics/dashboard')
    if (data.revenue_chart) revenueData.value = data.revenue_chart
    if (data.patient_flow) patientFlow.value = data.patient_flow
  } catch {}
})
</script>