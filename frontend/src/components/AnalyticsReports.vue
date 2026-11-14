<template>
  <div class="card p-5 space-y-4" data-testid="analytics-reports">
    <div>
      <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Tahliliy hisobotlar</h3>
      <p class="text-xs text-slate-400 mt-0.5">Daromad, bemorlar oqimi, shifokor yuklamasi va kelmay qolish: davr va filial bo'yicha, Excel va PDF.</p>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
      <div class="col-span-2"><label class="text-xs text-slate-400 block mb-1">Hisobot</label>
        <select v-model="kind" class="input" data-testid="rep-kind"><option v-for="k in kinds" :key="k.kind" :value="k.kind">{{ k.title }}</option></select></div>
      <div><label class="text-xs text-slate-400 block mb-1">Dan</label><input v-model="from" type="date" class="input" data-testid="rep-from" /></div>
      <div><label class="text-xs text-slate-400 block mb-1">Gacha</label><input v-model="to" type="date" class="input" data-testid="rep-to" /></div>
      <button class="btn-primary" :disabled="busy" data-testid="rep-view" @click="view">Ko'rish</button>
      <div class="flex gap-2">
        <button class="btn-secondary text-sm" :disabled="busy" data-testid="rep-xlsx" @click="download('xlsx')">Excel</button>
        <button class="btn-secondary text-sm" :disabled="busy" data-testid="rep-pdf" @click="download('pdf')">PDF</button>
      </div>
    </div>
    <label v-if="auth.can('branches:all')" class="flex items-center gap-2 text-sm"><input v-model="allBranches" type="checkbox" /> Hamma filial birga</label>

    <div v-if="report" class="space-y-5" data-testid="rep-result">
      <p class="text-xs text-slate-400">{{ report.title }} · {{ report.from }} - {{ report.to }} · {{ report.scope }}</p>
      <div v-for="s in report.sections" :key="s.title" class="space-y-1">
        <h4 class="text-sm font-semibold">{{ s.title }}</h4>
        <p v-if="!s.rows.length" class="text-xs text-slate-400">Ma'lumot yo'q</p>
        <div v-else class="table-container rounded-none border-0">
          <table class="table text-sm">
            <thead><tr><th v-for="c in s.columns" :key="c">{{ c }}</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in s.rows" :key="i"><td v-for="(v, j) in r" :key="j" :class="j > 0 && typeof v === 'number' ? 'text-right font-mono' : ''">{{ cell(v) }}</td></tr>
              <tr v-if="s.totals" class="font-semibold"><td v-for="(v, j) in s.totals" :key="j" :class="j > 0 && typeof v === 'number' ? 'text-right font-mono' : ''">{{ cell(v) }}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'

const toast = useToast(), theme = useThemeStore(), auth = useAuthStore()
const dark = computed(() => theme.isDark)
const kinds = ref([]), kind = ref('revenue'), busy = ref(false), report = ref(null), allBranches = ref(false)
const iso = d => d.toISOString().slice(0, 10)
const to = ref(iso(new Date())), from = ref(iso(new Date(Date.now() - 29 * 864e5)))
const cell = v => (v == null ? '—' : typeof v === 'number' ? new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 }).format(v) : v)
const params = () => ({ date_from: from.value, date_to: to.value, ...(allBranches.value ? { all_branches: true } : {}) })

async function view() {
  busy.value = true
  try { report.value = (await api.get(`/reports/analytics/${kind.value}`, { params: params() })).data } catch (e) { toast.error(e, "Hisobotni yuklab bo'lmadi") } finally { busy.value = false }
}
async function download(format) {
  busy.value = true
  try {
    const { data } = await api.get(`/reports/analytics/${kind.value}`, { params: { ...params(), format }, responseType: 'blob' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(data); a.download = `${kind.value}_${from.value}_${to.value}.${format}`
    document.body.appendChild(a); a.click(); a.remove()
  } catch (e) { toast.error(e, "Faylni yuklab bo'lmadi") } finally { busy.value = false }
}
onMounted(async () => { try { kinds.value = (await api.get('/reports/analytics')).data } catch { kinds.value = [] } })
</script>
