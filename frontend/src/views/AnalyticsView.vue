<template>
  <div class="space-y-5 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Tahlil</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Klinika faoliyati statistikasi va AI tahlili</p>
      </div>
      <div class="flex gap-2">
        <select v-model="period" :class="['input w-auto text-sm', dark ? '' : '']">
          <option value="week">Bu hafta</option>
          <option value="month">Bu oy</option>
          <option value="quarter">Kvartal</option>
          <option value="year">Yil</option>
        </select>
        <button @click="getAIInsight" :disabled="aiLoading" class="btn-primary text-sm">
          <Bot class="w-4 h-4" />{{ aiLoading ? 'Tahlil qilinmoqda...' : 'AI Tahlil' }}
        </button>
      </div>
    </div>

    <!-- 4 KPI cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div v-for="kpi in kpiCards" :key="kpi.label" class="card p-5 relative overflow-hidden">
        <div :class="['absolute top-0 right-0 w-20 h-20 rounded-full -mr-6 -mt-6 opacity-10']"
          :style="`background:rgb(var(--c-primary))`"></div>
        <div class="flex items-start justify-between mb-3">
          <div class="w-10 h-10 rounded-xl flex items-center justify-center" :class="kpi.bg">
            <component :is="kpi.icon" :class="['w-5 h-5', kpi.color]" />
          </div>
          <span :class="['text-xs font-semibold px-1.5 py-0.5 rounded-lg', kpi.upward ? 'text-emerald-500 bg-emerald-50 dark:bg-emerald-900/20' : 'text-red-500 bg-red-50 dark:bg-red-900/20']">
            {{ kpi.upward ? '↑' : '↓' }}{{ kpi.change }}
          </span>
        </div>
        <p :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ kpi.value }}</p>
        <p :class="['text-xs mt-1', dark ? 'text-slate-400' : 'text-slate-500']">{{ kpi.label }}</p>
        <!-- Mini sparkline -->
        <div class="flex items-end gap-0.5 mt-3 h-6">
          <div v-for="(v, i) in kpi.spark" :key="i"
            class="flex-1 rounded-t transition-all duration-700"
            :style="`height:${v}%; background:rgba(var(--c-primary),.${i === kpi.spark.length-1 ? '9' : '4'})`"></div>
        </div>
      </div>
    </div>

    <!-- Main charts grid -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">

      <!-- Top Diagnoses -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">🏥 Eng ko'p tashxislar</h3>
        <div class="space-y-3">
          <div v-for="(d, i) in analytics.top_diagnoses" :key="d.name" class="flex items-center gap-3">
            <span :class="['w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0']"
              :style="`background:rgba(var(--c-primary),${1 - i*0.15})`">{{ i+1 }}</span>
            <div class="flex-1">
              <div class="flex justify-between mb-1">
                <span :class="['text-sm font-medium', dark ? 'text-slate-200' : 'text-slate-800']">{{ d.name }}</span>
                <span :class="['text-xs', dark ? 'text-slate-400' : 'text-slate-500']">{{ d.count }} ta</span>
              </div>
              <div :class="['h-2 rounded-full overflow-hidden', dark ? 'bg-slate-800' : 'bg-slate-100']">
                <div class="h-full rounded-full transition-all duration-700"
                  :style="`width:${(d.count/analytics.top_diagnoses[0].count)*100}%; background:rgba(var(--c-primary),${1-i*0.1})`"></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Top Doctors -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">👨‍⚕️ Faol shifokorlar</h3>
        <div class="space-y-3">
          <div v-for="d in analytics.top_doctors" :key="d.name"
            :class="['flex items-center justify-between p-3 rounded-xl border transition-colors', dark ? 'border-slate-800 hover:bg-slate-800/50' : 'border-slate-100 hover:bg-slate-50']">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-xl flex items-center justify-center text-xs font-bold text-white shadow-sm"
                :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
                {{ d.name.split(' ')[1]?.[0] || 'D' }}
              </div>
              <div>
                <p :class="['text-sm font-medium', dark ? 'text-slate-200' : 'text-slate-900']">{{ d.name }}</p>
                <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">{{ d.department }}</p>
              </div>
            </div>
            <div class="text-right">
              <p :class="['text-sm font-bold', dark ? 'text-white' : 'text-slate-900']">{{ d.patients }}</p>
              <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">bemor</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Monthly visits bar chart -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">📅 Oylik qabullar</h3>
        <div class="flex items-end gap-2 h-40">
          <div v-for="m in monthlyData" :key="m.month" class="flex-1 flex flex-col items-center gap-1 group">
            <span :class="['text-[10px] opacity-0 group-hover:opacity-100 transition-opacity font-semibold', dark ? 'text-slate-300' : 'text-slate-600']">{{ m.count }}</span>
            <div class="w-full rounded-t-lg transition-all duration-700 cursor-pointer hover:opacity-90"
              :style="`height:${(m.count/maxMonthly)*100}%; background:linear-gradient(to top,rgb(var(--c-primary)),rgb(var(--c-secondary)))`"></div>
            <span :class="['text-[10px]', dark ? 'text-slate-500' : 'text-slate-400']">{{ m.month }}</span>
          </div>
        </div>
      </div>

      <!-- Patient age distribution -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">👥 Yosh taqsimoti</h3>
        <div class="space-y-3">
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

        <!-- Revenue by department donut -->
        <div class="mt-5 pt-4 border-t" :class="dark ? 'border-slate-800' : 'border-slate-100'">
          <h4 :class="['text-sm font-semibold mb-3', dark ? 'text-slate-300' : 'text-slate-700']">Bo'limlar bo'yicha daromad</h4>
          <div class="space-y-2">
            <div v-for="dep in departments" :key="dep.name" class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <div class="w-2.5 h-2.5 rounded-full" :style="`background:${dep.color}`"></div>
                <span :class="['text-xs', dark ? 'text-slate-400' : 'text-slate-600']">{{ dep.name }}</span>
              </div>
              <span :class="['text-xs font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">{{ dep.pct }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

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
import { ref, computed } from 'vue'
import { Users, Calendar, TrendingUp, Activity, Bot, X } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useThemeStore } from '@/stores/theme'

const theme  = useThemeStore()
const dark   = computed(() => theme.isDark)
const period = ref('month')


const aiLoading = ref(false)
const aiInsight = ref('')
const aiDemo = ref(false)

const kpiCards = [
  { label: 'Jami bemorlar',   value: '1,247', change: '12%',  upward: true,  icon: Users,      bg: 'bg-blue-50 dark:bg-blue-900/20',    color: 'text-blue-500',    spark: [40,55,45,60,50,70,85] },
  { label: 'Bu oydagi qabul', value: '384',   change: '8%',   upward: true,  icon: Calendar,   bg: 'bg-violet-50 dark:bg-violet-900/20', color: 'text-violet-500',  spark: [60,50,70,55,75,65,90] },
  { label: 'Daromad (UZS)',   value: '48.2M', change: '15%',  upward: true,  icon: TrendingUp, bg: 'bg-emerald-50 dark:bg-emerald-900/20',color: 'text-emerald-500', spark: [45,55,65,50,70,60,100] },
  { label: 'Bemorlar sog\'l.', value: '94%',  change: '2%',   upward: false, icon: Activity,   bg: 'bg-amber-50 dark:bg-amber-900/20',   color: 'text-amber-500',   spark: [80,85,90,82,88,92,94] },
]

const analytics = ref({
  top_diagnoses: [
    { name: 'Gipertenziya',      count: 145 },
    { name: 'Diabet 2-tur',      count: 112 },
    { name: 'ARVI',              count: 98  },
    { name: 'Gastrit',           count: 87  },
    { name: 'Osteoxondroz',      count: 63  },
  ],
  top_doctors: [
    { name: 'Dr. Rustamov', department: 'Kardiologiya', patients: 124 },
    { name: 'Dr. Karimov',  department: 'Nevrologiya',  patients: 98  },
    { name: 'Dr. Yusupov',  department: 'Dermatologiya',patients: 76  },
  ],
})

const monthlyData = [
  { month: 'Sen', count: 210 },
  { month: 'Okt', count: 245 },
  { month: 'Noy', count: 198 },
  { month: 'Dek', count: 290 },
  { month: 'Yan', count: 315 },
  { month: 'Fev', count: 384 },
]
const maxMonthly = computed(() => Math.max(...monthlyData.map(m => m.count)))

const ageGroups = [
  { label: '0–17',   pct: 12 },
  { label: '18–35',  pct: 28 },
  { label: '36–55',  pct: 38 },
  { label: '56–70',  pct: 15 },
  { label: '70+',    pct: 7  },
]

const departments = computed(() => [
  { name: 'Kardiologiya',  pct: 35, color: `rgb(var(--c-primary))` },
  { name: 'Nevrologiya',   pct: 25, color: `rgba(var(--c-secondary),.8)` },
  { name: 'Dermatologiya', pct: 20, color: '#10b981' },
  { name: 'Umumiy amaliyot', pct: 20, color: '#f59e0b' },
])

async function getAIInsight() {
  aiLoading.value = true
  aiInsight.value = ''

  const statsText = `
Klinika statistikasi (${period.value}):
- Jami bemorlar: 1,247 (+12%)
- Bu oydagi qabullar: 384 (+8%)
- Daromad: 48.2 mln UZS (+15%)
- Eng ko'p tashxislar: Gipertenziya (145), Diabet 2-tur (112), ARVI (98), Gastrit (87)
- Faol shifokorlar: Dr. Rustamov (124 bemor), Dr. Karimov (98), Dr. Yusupov (76)
- Yosh taqsimoti: 0-17: 12%, 18-35: 28%, 36-55: 38%, 56-70: 15%, 70+: 7%
- To'lov usullari: Naqd: 45%, Karta: 35%, O'tkazma: 20%
`

  try {
    const { data } = await api.post('/ai/analyze', { period: period.value, stats: statsText })
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