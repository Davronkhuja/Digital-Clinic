<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 class="text-2xl font-heading font-bold text-slate-900">Hisobotlar</h2>
      <p class="text-slate-500 text-sm mt-1">PDF va Excel hisobotlar generatsiyasi</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-4">
      <div v-for="r in reports" :key="r.id" class="card p-5 hover:shadow-card-hover transition-shadow">
        <div class="flex items-start justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center" :class="r.bg">
              <component :is="r.icon" class="w-5 h-5" :class="r.color" />
            </div>
            <div>
              <h3 class="font-semibold text-slate-900 text-sm">{{ r.name }}</h3>
              <p class="text-xs text-slate-500 mt-0.5">Oxirgi: {{ r.last_generated }}</p>
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
import { ref } from 'vue'
import { FileBarChart, DollarSign, Users, Calendar, FileDown, CheckCircle } from 'lucide-vue-next'
import api from '@/composables/useApi'

const generating = ref(null)
const generated = ref({})
const errors = ref({})

const reports = [
  { id: '1', name: 'Oylik moliyaviy hisobot', last_generated: '2026-02-01', desc: 'Daromad, xarajat va sof foyda ko\'rsatkichlari', bg: 'bg-emerald-50', color: 'text-emerald-500', icon: DollarSign },
  { id: '2', name: 'Bemorlar statistikasi', last_generated: '2026-02-15', desc: 'Yangi va qayta bemorlar, demografiya tahlili', bg: 'bg-blue-50', color: 'text-blue-500', icon: Users },
  { id: '3', name: 'Xodimlar faoliyati', last_generated: '2026-02-20', desc: 'Shifokorlar ish natijalari va reyting', bg: 'bg-purple-50', color: 'text-purple-500', icon: FileBarChart },
  { id: '4', name: 'Uchrashuvlar tahlili', last_generated: '2026-02-22', desc: 'Qabul qilingan, bekor qilingan uchrashuvlar', bg: 'bg-amber-50', color: 'text-amber-500', icon: Calendar },
]

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
