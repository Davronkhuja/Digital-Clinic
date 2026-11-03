<template>
  <div class="space-y-5 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Finance</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Track revenue and expenses</p>
    </div>

    <!-- Period -->
    <div class="flex gap-1">
      <button v-for="p in periods" :key="p.value" @click="setPeriod(p.value)"
        :class="['px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors',
          period === p.value ? 'text-white border-transparent' : dark ? 'border-slate-700 text-slate-300 hover:bg-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50']"
        :style="period === p.value ? 'background:rgb(var(--c-primary))' : ''">
        {{ p.label }}
      </button>
    </div>

    <EmptyState v-if="loadError" title="Moliya ma'lumotlarini yuklab bo'lmadi" description="Serverga ulanishni tekshirib, qayta urinib ko'ring" actionLabel="Qayta urinish" @action="loadAll" />
    <template v-else>

    <!-- 4 stat cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div v-for="s in statCards" :key="s.label" class="card p-5">
        <div :class="['w-10 h-10 rounded-xl flex items-center justify-center mb-3', s.iconBg]">
          <component :is="s.icon" :class="['w-5 h-5', s.iconColor]" />
        </div>
        <p :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ s.value }}</p>
        <p :class="['text-xs mt-1', dark ? 'text-slate-400' : 'text-slate-500']">{{ s.label }}</p>
      </div>
    </div>

    <!-- Tabs -->
    <div :class="['flex gap-1 border-b', dark ? 'border-slate-800' : 'border-slate-200']">
      <button v-for="tab in tabs" :key="tab"
        @click="activeTab = tab"
        :class="['px-4 py-2.5 text-sm font-medium border-b-2 transition-all -mb-px',
          activeTab === tab
            ? 'border-current font-semibold'
            : dark ? 'border-transparent text-slate-400 hover:text-slate-300' : 'border-transparent text-slate-500 hover:text-slate-700']"
        :style="activeTab === tab ? 'color:rgb(var(--c-primary)); border-color:rgb(var(--c-primary))' : ''">
        {{ tab }}
      </button>
    </div>

    <!-- ═══ Overview ═══════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'Overview'" class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- Bar chart: Revenue vs Expenses -->
      <div class="card p-5 lg:col-span-2">
        <h3 :class="['font-semibold mb-5', dark ? 'text-white' : 'text-slate-900']">Revenue vs Expenses</h3>
        <EmptyState v-if="!loading && chartData.length === 0" title="Ma'lumot yo'q" description="Tranzaksiyalar qo'shilgach grafik shu yerda chiqadi" />
        <div v-else class="flex items-end gap-6 h-52">
          <div v-for="month in chartData" :key="month.name" class="flex-1 flex flex-col items-center gap-1">
            <div class="flex items-end gap-1 w-full h-40">
              <div class="flex-1 rounded-t-lg transition-all duration-700 relative group"
                :style="`height:${(month.revenue / chartMax) * 100}%; background:rgb(var(--c-primary))`">
                <div class="absolute -top-7 left-1/2 -translate-x-1/2 text-[10px] font-semibold opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap" :class="dark ? 'text-slate-300' : 'text-slate-600'">
                  {{ fmtShort(month.revenue) }}
                </div>
              </div>
              <div class="flex-1 rounded-t-lg transition-all duration-700 relative group"
                :style="`height:${(month.expense / chartMax) * 100}%; background:rgba(var(--c-primary)/.35)`">
                <div class="absolute -top-7 left-1/2 -translate-x-1/2 text-[10px] font-semibold opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap" :class="dark ? 'text-slate-300' : 'text-slate-600'">
                  {{ fmtShort(month.expense) }}
                </div>
              </div>
            </div>
            <span :class="['text-xs', dark ? 'text-slate-400' : 'text-slate-500']">{{ month.name }}</span>
          </div>
        </div>
        <div class="flex gap-4 mt-3">
          <span class="flex items-center gap-1.5 text-xs" :class="dark ? 'text-slate-400' : 'text-slate-500'">
            <span class="w-3 h-2 rounded-sm inline-block" :style="`background:rgb(var(--c-primary))`"></span> Revenue
          </span>
          <span class="flex items-center gap-1.5 text-xs" :class="dark ? 'text-slate-400' : 'text-slate-500'">
            <span class="w-3 h-2 rounded-sm inline-block" :style="`background:rgba(var(--c-primary)/.35)`"></span> Expenses
          </span>
        </div>
      </div>

      <!-- Kategoriyalar bo'yicha -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-5', dark ? 'text-white' : 'text-slate-900']">Kategoriyalar</h3>
        <EmptyState v-if="!loading && categoryTotals.length === 0" title="Ma'lumot yo'q" />
        <div v-else class="space-y-3">
          <div v-for="c in categoryTotals" :key="c.type + c.name">
            <div class="flex items-center justify-between mb-1">
              <span :class="['text-sm', dark ? 'text-slate-300' : 'text-slate-600']">{{ c.name }}</span>
              <span :class="['text-sm font-semibold', c.type === 'income' ? 'text-emerald-500' : 'text-red-500']">{{ c.type === 'income' ? '' : '−' }}{{ fmt(c.total) }}</span>
            </div>
            <div :class="['h-1.5 rounded-full', dark ? 'bg-slate-800' : 'bg-slate-100']">
              <div class="h-full rounded-full" :class="c.type === 'income' ? 'bg-emerald-500' : 'bg-red-400'" :style="`width:${(c.total / categoryMax) * 100}%`"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ Transactions ════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'Transactions'" class="card">
      <div :class="['p-4 border-b flex gap-3 flex-wrap items-center', dark ? 'border-slate-800' : 'border-slate-100']">
        <div class="relative flex-1 min-w-48">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input v-model="txSearch" class="input pl-9" placeholder="Search transactions..." />
        </div>
        <select v-model="typeFilter" class="input w-auto" @change="loadTransactions">
          <option value="">Barchasi</option>
          <option value="income">Daromad</option>
          <option value="expense">Xarajat</option>
        </select>
        <button @click="exportTransactions" :class="['flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition-colors', dark ? 'border-slate-700 text-slate-300 hover:bg-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50']">
          <Download class="w-4 h-4" /> Export
        </button>
        <button class="btn-primary text-sm" @click="openModal"><Plus class="w-4 h-4" /> Add</button>
      </div>

      <div class="table-container border-0 rounded-none">
        <table class="table">
          <thead>
            <tr>
              <th>Sana</th>
              <th>Patient</th>
              <th>Service</th>
              <th>Kategoriya</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in filteredTx" :key="t.id">
              <td :class="['font-mono text-xs', dark ? 'text-slate-400' : 'text-slate-500']">{{ t.date }}</td>
              <td :class="['font-medium', dark ? 'text-slate-200' : 'text-slate-900']">{{ t.patient_name || '—' }}</td>
              <td :class="dark ? 'text-slate-400' : 'text-slate-600'">{{ t.description }}</td>
              <td :class="dark ? 'text-slate-400' : 'text-slate-600'">{{ t.category || '—' }}</td>
              <td :class="['font-mono font-semibold', t.type === 'income' ? 'text-emerald-500' : 'text-red-500']">
                {{ t.type === 'income' ? '' : '−' }}{{ fmt(t.amount) }}
              </td>
            </tr>
            <tr v-if="loading">
              <td colspan="5" :class="['py-10 text-center text-sm', dark ? 'text-slate-500' : 'text-slate-400']">Yuklanmoqda...</td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-if="!loading && transactions.length === 0" title="Hali tranzaksiyalar yo'q" description="Birinchi daromad yoki xarajatni qo'shing" actionLabel="Tranzaksiya qo'shish" @action="openModal" />
      <p v-else-if="!loading && filteredTx.length === 0" :class="['py-10 text-center text-sm', dark ? 'text-slate-500' : 'text-slate-400']">No transactions found</p>
    </div>

    </template>

    <!-- Add Transaction Modal -->
    <Transition name="modal-fade">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div :class="['w-full max-w-md rounded-2xl shadow-2xl overflow-hidden animate-fade-in', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']" @click.stop>
          <div :class="['flex items-center justify-between px-6 py-4 border-b', dark ? 'border-slate-800' : 'border-slate-200']">
            <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Yangi tranzaksiya</h3>
            <button @click="closeModal" :class="['p-1.5 rounded-lg', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><X class="w-4 h-4" /></button>
          </div>
          <div class="p-6 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label :class="lbl">Tur *</label>
                <select v-model="form.type" class="input">
                  <option value="income">Daromad</option>
                  <option value="expense">Xarajat</option>
                </select>
              </div>
              <div>
                <label :class="lbl">Summa (UZS) *</label>
                <input :value="formattedAmount" @input="onAmountInput" class="input font-mono" placeholder="250 000" inputmode="numeric" />
              </div>
            </div>
            <div>
              <label :class="lbl">Tavsif *</label>
              <input v-model="form.description" class="input" placeholder="Konsultatsiya to'lovi" />
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label :class="lbl">Bemor</label>
                <select v-model="form.patient_id" class="input">
                  <option value="">— Tanlanmagan —</option>
                  <option v-for="p in patientList" :key="p.id" :value="p.id">{{ p.name }}</option>
                </select>
              </div>
              <div>
                <label :class="lbl">Kategoriya</label>
                <select v-model="form.category" class="input">
                  <option>Consultation</option><option>Surgery</option><option>Lab</option>
                  <option>Equipment</option><option>Salary</option><option>Other</option>
                </select>
              </div>
            </div>
            <div>
              <label :class="lbl">Sana</label>
              <input v-model="form.date" type="date" class="input" />
            </div>
          </div>
          <div :class="['px-6 py-4 border-t flex gap-3', dark ? 'border-slate-800 bg-slate-900/50' : 'border-slate-100 bg-slate-50']">
            <button class="btn-secondary flex-1" @click="closeModal">Bekor</button>
            <button class="btn-primary flex-1" @click="addTransaction" :disabled="saving">
              <Check class="w-4 h-4" />{{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import { Plus, Search, X, TrendingUp, TrendingDown, DollarSign, CreditCard, Check, Download } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import api, { fetchAll } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast()

const theme = useThemeStore()
const dark  = computed(() => theme.isDark)
const lbl   = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])

const activeTab = ref('Overview')
const tabs = ['Overview', 'Transactions']

const periods = [
  { value: 'week', label: 'Hafta' },
  { value: 'month', label: 'Oy' },
  { value: 'year', label: 'Yil' },
  { value: 'all', label: 'Hammasi' },
]
const period = ref('month')

const loading = ref(true)
const loadError = ref(false)
const summary = ref(null)
const transactions = ref([])
const typeFilter = ref('')
const txSearch = ref('')
const patientList = ref([])
const showModal = ref(false)
const saving = ref(false)

const defaultForm = () => ({
  type: 'income', amount: '', description: '', patient_id: '',
  category: 'Consultation',
  date: new Date().toISOString().slice(0, 10)
})
const form = reactive(defaultForm())

const formattedAmount = computed(() => form.amount ? new Intl.NumberFormat('uz-UZ').format(form.amount) : '')
function onAmountInput(e) {
  const raw = e.target.value.replace(/\D/g, '')
  form.amount = raw ? parseInt(raw) : ''
  e.target.value = raw ? new Intl.NumberFormat('uz-UZ').format(parseInt(raw)) : ''
}

const currency = computed(() => summary.value?.currency || 'UZS')
function fmt(v) { return new Intl.NumberFormat('uz-UZ').format(v) + ' ' + currency.value }
function fmtShort(v) { return v >= 1000 ? (v / 1000).toFixed(0) + 'K' : v }

// ── Stat cards (/finance/summary) ─────────────────
const statCards = computed(() => {
  const s = summary.value
  const val = v => (s ? fmt(v) : '—')
  return [
    { label: 'Daromad', value: val(s?.total_income), icon: TrendingUp, iconBg: 'bg-emerald-50 dark:bg-emerald-900/30', iconColor: 'text-emerald-500' },
    { label: 'Xarajat', value: val(s?.total_expense), icon: TrendingDown, iconBg: 'bg-red-50 dark:bg-red-900/30', iconColor: 'text-red-400' },
    { label: 'Sof foyda', value: val(s?.net_profit), icon: CreditCard, iconBg: 'bg-cyan-50 dark:bg-cyan-900/30', iconColor: 'text-cyan-500' },
    { label: 'Tranzaksiyalar', value: s ? String(s.transactions_count) : '—', icon: DollarSign, iconBg: 'bg-blue-50 dark:bg-blue-900/30', iconColor: 'text-blue-500' },
  ]
})

// ── Grafik: tranzaksiyalardan oy bo'yicha ─────────
const chartData = computed(() => {
  const months = {}
  for (const t of transactions.value) {
    const key = (t.date || '').slice(0, 7)
    if (!key) continue
    const m = months[key] ||= { name: key, revenue: 0, expense: 0 }
    if (t.type === 'income') m.revenue += t.amount
    else m.expense += t.amount
  }
  return Object.values(months).sort((a, b) => a.name.localeCompare(b.name)).slice(-6)
})
const chartMax = computed(() => Math.max(1, ...chartData.value.flatMap(m => [m.revenue, m.expense])))

const categoryTotals = computed(() => {
  const totals = {}
  for (const t of transactions.value) {
    const name = t.category || 'Other'
    const c = totals[t.type + '|' + name] ||= { type: t.type, name, total: 0 }
    c.total += t.amount
  }
  return Object.values(totals).sort((a, b) => b.total - a.total)
})
const categoryMax = computed(() => Math.max(1, ...categoryTotals.value.map(c => c.total)))

const filteredTx = computed(() => {
  const q = txSearch.value.toLowerCase()
  if (!q) return transactions.value
  return transactions.value.filter(t =>
    (t.patient_name || '').toLowerCase().includes(q) ||
    (t.description || '').toLowerCase().includes(q) ||
    (t.category || '').toLowerCase().includes(q)
  )
})

async function loadSummary() {
  const { data } = await api.get('/finance/summary', { params: { period: period.value } })
  summary.value = data
}

async function loadTransactions() {
  loading.value = true
  try {
    const { data } = await api.get('/finance/transactions', { params: typeFilter.value ? { type: typeFilter.value } : {} })
    transactions.value = data
  } catch (e) {
    transactions.value = []
    loadError.value = true
    toast.error(e, "Tranzaksiyalarni yuklab bo'lmadi")
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  loadError.value = false
  summary.value = null
  try {
    await loadSummary()
  } catch (e) {
    loadError.value = true
    toast.error(e, "Moliyaviy xulosani yuklab bo'lmadi")
  }
  await loadTransactions()
}

async function setPeriod(p) {
  period.value = p
  try { await loadSummary() } catch (e) { toast.error(e, "Moliyaviy xulosani yuklab bo'lmadi") }
}

function openModal() { Object.assign(form, defaultForm()); showModal.value = true }
function closeModal() { showModal.value = false }

async function addTransaction() {
  if (!form.description || !form.amount) return
  saving.value = true
  try {
    await api.post('/finance/transactions', {
      type: form.type, amount: Number(form.amount), description: form.description,
      category: form.category, date: form.date, patient_id: form.patient_id || null,
    })
    toast.success('Tranzaksiya saqlandi')
    closeModal()
    await loadAll()
  } catch (e) {
    toast.error(e, "Tranzaksiyani saqlab bo'lmadi")
  } finally {
    saving.value = false
  }
}

function exportTransactions() {
  const header = ['Date', 'Patient', 'Service', 'Category', 'Type', 'Amount']
  const rows = filteredTx.value.map(t => [t.date, t.patient_name || '', t.description, t.category || '', t.type, t.amount])
  const csv = [header, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' }))
  a.download = `transactions_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
}

onMounted(async () => {
  try {
    patientList.value = await fetchAll('/patients')
  } catch (e) {
    toast.error(e, "Bemorlar ro'yxatini yuklab bo'lmadi")
  }
  await loadAll()
})
</script>

<style scoped>
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>