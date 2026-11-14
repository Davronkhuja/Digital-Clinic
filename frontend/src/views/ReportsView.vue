<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 class="text-2xl font-heading font-bold text-slate-900">Hisobotlar</h2>
      <p class="text-slate-500 text-sm mt-1">PDF va Excel hisobotlar generatsiyasi</p>
    </div>

    <AnalyticsReports />

    <AccountingExport v-if="auth.can('exports:read')" />

    <div v-if="loadError" class="card">
      <EmptyState title="Hisobotlar ro'yxatini yuklab bo'lmadi" description="Serverga ulanishni tekshirib, qayta urinib ko'ring" action-label="Qayta urinish" @action="loadReports" />
    </div>
    <div v-else-if="loading" class="text-sm text-slate-500">Yuklanmoqda...</div>
    <div v-else-if="reports.length === 0" class="card">
      <EmptyState title="Hisobotlar mavjud emas" description="Hozircha yaratish mumkin bo'lgan hisobot turlari yo'q" />
    </div>
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
      <div v-for="r in reports" :key="r.id" class="card p-5 hover:shadow-card-hover transition-shadow">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center" :class="r.bg">
              <component :is="r.icon" class="w-5 h-5" :class="r.color" />
            </div>
            <div>
              <h3 class="font-semibold text-slate-900 text-sm">{{ r.name }}</h3>
            </div>
          </div>
          <span class="badge badge-slate text-xs">CSV</span>
        </div>
        <p class="text-xs text-slate-500 mt-3">{{ r.desc }}</p>
        <div class="mt-4 flex gap-2">
          <button class="btn-primary text-xs flex-1 justify-center" @click="generate(r.id, r.name)" :disabled="generating === r.id">
            <span v-if="generating === r.id">Yaratilmoqda...</span>
            <span v-else><FileDown class="w-3.5 h-3.5" /> Yaratish</span>
          </button>
          <button class="btn-secondary text-xs">Ko'rish</button>
        </div>
        <p v-if="errors[r.id]" class="mt-2 text-xs text-red-500">{{ errors[r.id] }}</p>
        <div v-if="generated[r.id]" class="mt-2 p-2 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center gap-2">
          <CheckCircle class="w-3.5 h-3.5 text-emerald-500" />
          <span class="text-xs text-emerald-600">Hisobot tayyor!</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { FileBarChart, DollarSign, Users, Calendar, FileDown, CheckCircle } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/ui/EmptyState.vue'
import AccountingExport from '@/components/AccountingExport.vue'
import AnalyticsReports from '@/components/AnalyticsReports.vue'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()

const generating = ref(null)
const generated = ref({})
const errors = ref({})

const toast = useToast()
const reports = ref([])
const loading = ref(true)
const loadError = ref(false)

// Hisobot turi bo'yicha ikonka/rang/tavsif
const typeMeta = {
  finance: { bg: 'bg-emerald-50', color: 'text-emerald-500', icon: DollarSign, desc: "Daromad, xarajat va sof foyda ko'rsatkichlari" },
  patients: { bg: 'bg-blue-50', color: 'text-blue-500', icon: Users, desc: 'Yangi va qayta bemorlar, demografiya tahlili' },
  staff: { bg: 'bg-purple-50', color: 'text-purple-500', icon: FileBarChart, desc: 'Shifokorlar ish natijalari va reyting' },
  appointments: { bg: 'bg-amber-50', color: 'text-amber-500', icon: Calendar, desc: "Qabul qilingan, bekor qilingan uchrashuvlar" },
}
const defaultMeta = { bg: 'bg-slate-100', color: 'text-slate-500', icon: FileBarChart, desc: '' }

async function loadReports() {
  loading.value = true
  loadError.value = false
  try {
    const { data } = await api.get('/reports')
    reports.value = (data.reports || []).map(r => ({ ...r, ...(typeMeta[r.type] || defaultMeta) }))
  } catch (e) {
    reports.value = []
    loadError.value = true
    toast.error(e, "Hisobotlar ro'yxatini yuklab bo'lmadi")
  } finally {
    loading.value = false
  }
}

onMounted(loadReports)

async function generate(id, name) {
  generating.value = id
  errors.value[id] = ''
  try {
    await api.post(`/reports/generate/${id}`)
    const res = await api.get(`/reports/download/${id}`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `${name.replace(/\s+/g, '_')}_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    generated.value[id] = true
    setTimeout(() => { generated.value[id] = false }, 3000)
  } catch (e) {
    errors.value[id] = e.response?.data?.detail || "Hisobotni yuklab bo'lmadi"
  } finally {
    generating.value = null
  }
}
</script>
