<template>
  <div class="space-y-5 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Finance</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Track revenue, expenses, and commissions</p>
    </div>

    <!-- 4 stat cards -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div v-for="s in statCards" :key="s.label" class="card p-5">
        <div class="flex items-start justify-between mb-3">
          <div :class="['w-10 h-10 rounded-xl flex items-center justify-center', s.iconBg]">
            <component :is="s.icon" :class="['w-5 h-5', s.iconColor]" />
          </div>
          <span :class="['text-xs font-semibold', s.positive ? 'text-emerald-500' : 'text-red-500']">
            {{ s.positive ? '↑' : '↓' }}{{ s.change }}
          </span>
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
        <div class="flex items-end gap-6 h-52">
          <div v-for="month in chartData" :key="month.name" class="flex-1 flex flex-col items-center gap-1">
            <div class="flex items-end gap-1 w-full h-40">
              <div class="flex-1 rounded-t-lg transition-all duration-700 relative group"
                :style="`height:${(month.revenue / 60000) * 100}%; background:rgb(var(--c-primary))`">
                <div class="absolute -top-7 left-1/2 -translate-x-1/2 text-[10px] font-semibold opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap" :class="dark ? 'text-slate-300' : 'text-slate-600'">
                  {{ fmtShort(month.revenue) }}
                </div>
              </div>
              <div class="flex-1 rounded-t-lg transition-all duration-700 relative group"
                :style="`height:${(month.expense / 60000) * 100}%; background:rgba(var(--c-primary)/.35)`">
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

      <!-- Donut chart: Payment Methods -->
      <div class="card p-5">
        <h3 :class="['font-semibold mb-5', dark ? 'text-white' : 'text-slate-900']">Payment Methods</h3>
        <!-- SVG donut -->
        <div class="flex justify-center mb-4">
          <svg width="130" height="130" viewBox="0 0 42 42">
            <circle cx="21" cy="21" r="15.915" fill="none" stroke="#e2e8f0" stroke-width="5" />
            <circle cx="21" cy="21" r="15.915" fill="none"
              :stroke="`rgb(var(--c-secondary))`" stroke-width="5"
              stroke-dasharray="45 55" stroke-dashoffset="25"
              style="transform-origin:center;transform:rotate(-90deg);transition:stroke-dasharray .8s ease" />
            <circle cx="21" cy="21" r="15.915" fill="none"
              :stroke="`rgba(var(--c-primary)/.7)`" stroke-width="5"
              stroke-dasharray="35 65" stroke-dashoffset="-20"
              style="transform-origin:center;transform:rotate(-90deg);transition:stroke-dasharray .8s ease" />
            <circle cx="21" cy="21" r="15.915" fill="none"
              stroke="#10b981" stroke-width="5"
              stroke-dasharray="20 80" stroke-dashoffset="-55"
              style="transform-origin:center;transform:rotate(-90deg);transition:stroke-dasharray .8s ease" />
          </svg>
        </div>
        <div class="space-y-2">
          <div v-for="pm in paymentMethods" :key="pm.label" class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full" :style="`background:${pm.color}`"></span>
              <span :class="['text-sm', dark ? 'text-slate-300' : 'text-slate-600']">{{ pm.label }}</span>
            </div>
            <span :class="['text-sm font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">{{ pm.pct }}%</span>
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
        <button :class="['flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition-colors', dark ? 'border-slate-700 text-slate-300 hover:bg-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50']">
          <Filter class="w-4 h-4" /> Filter
        </button>
        <button @click="exportTransactions" :class="['flex items-center gap-2 px-4 py-2 rounded-xl border text-sm font-medium transition-colors', dark ? 'border-slate-700 text-slate-300 hover:bg-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50']">
          <Download class="w-4 h-4" /> Export
        </button>
        <button class="btn-primary text-sm" @click="openModal"><Plus class="w-4 h-4" /> Add</button>
      </div>

      <div class="table-container border-0 rounded-none">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Patient</th>
              <th>Service</th>
              <th>Amount</th>
              <th>Method</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in filteredTx" :key="t.id">
              <td>
                <span :class="['font-mono text-xs font-semibold', dark ? 'text-slate-400' : 'text-slate-400']">{{ t.txn_id }}</span>
              </td>
              <td :class="['font-medium', dark ? 'text-slate-200' : 'text-slate-900']">{{ t.patient_name || '—' }}</td>
              <td :class="dark ? 'text-slate-400' : 'text-slate-600'">{{ t.description }}</td>
              <td :class="['font-mono font-semibold', t.type === 'income' ? 'text-emerald-500' : 'text-red-500']">
                {{ t.type === 'income' ? '' : '−' }}{{ fmt(t.amount) }}
              </td>
              <td>
                <span :class="['text-sm font-medium', dark ? 'text-slate-300' : 'text-slate-600']">{{ t.method || 'Cash' }}</span>
              </td>
              <td>
                <span :class="['badge text-xs font-semibold', t.status === 'Paid' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400' : t.status === 'Pending' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400' : 'bg-red-100 text-red-600']">
                  {{ t.status || 'Paid' }}
                </span>
              </td>
              <td>
                <button @click="deleteTransaction(t.id)" class="p-1.5 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"><Trash2 class="w-3.5 h-3.5" /></button>
              </td>
            </tr>
            <tr v-if="filteredTx.length === 0">
              <td colspan="7" :class="['py-10 text-center text-sm', dark ? 'text-slate-500' : 'text-slate-400']">No transactions found</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ═══ Commissions ═════════════════════════════════════════════════════ -->
    <div v-if="activeTab === 'Commissions'" class="card">
      <div :class="['px-5 py-4 border-b', dark ? 'border-slate-800' : 'border-slate-100']">
        <h3 :class="['font-semibold', dark ? 'text-white' : 'text-slate-900']">Doctor Commissions</h3>
      </div>
      <div class="table-container border-0 rounded-none">
        <table class="table">
          <thead>
            <tr>
              <th>Doctor</th>
              <th>Patients</th>
              <th>Revenue</th>
              <th>Rate</th>
              <th>Earned</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in commissions" :key="c.doctor">
              <td>
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white"
                    :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
                    {{ c.doctor.split('.')[1]?.trim()[0] || 'D' }}
                  </div>
                  <span :class="['font-medium', dark ? 'text-slate-200' : 'text-slate-900']">{{ c.doctor }}</span>
                </div>
              </td>
              <td :class="dark ? 'text-slate-400' : 'text-slate-600'">{{ c.patients }}</td>
              <td :class="['font-mono font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">{{ fmt(c.revenue) }}</td>
              <td>
                <span class="badge text-xs font-semibold" :style="`background:rgba(var(--c-primary)/.15);color:rgb(var(--c-primary))`">{{ c.rate }}%</span>
              </td>
              <td :class="['font-mono font-bold text-emerald-500']">{{ fmt(Math.round(c.revenue * c.rate / 100)) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

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
                <select v-model="form.patient_name" class="input">
                  <option value="">— Tanlanmagan —</option>
                  <option v-for="p in patientList" :key="p" :value="p">{{ p }}</option>
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
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label :class="lbl">To'lov usuli</label>
                <select v-model="form.method" class="input">
                  <option>Cash</option><option>Card</option><option>Transfer</option>
                </select>
              </div>
              <div>
                <label :class="lbl">Status</label>
                <select v-model="form.status" class="input">
                  <option>Paid</option><option>Pending</option><option>Cancelled</option>
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
import { Plus, Search, X, TrendingUp, TrendingDown, DollarSign, BarChart3, CreditCard, Trash2, Check, Filter, Download } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import api, { fetchAll } from '@/composables/useApi'

const theme = useThemeStore()
const dark  = computed(() => theme.isDark)
const lbl   = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])

const activeTab = ref('Overview')
const tabs = ['Overview', 'Transactions', 'Commissions']

// ── Stat cards ────────────────────────────────────
const statCards = [
  { label: 'Revenue Today',   value: "$4,850",  change: '+18%',  positive: true,  icon: DollarSign, iconBg: 'bg-blue-50 dark:bg-blue-900/30',    iconColor: 'text-blue-500' },
  { label: 'Monthly Revenue', value: "$48,250", change: '+12.5%',positive: true,  icon: TrendingUp, iconBg: 'bg-emerald-50 dark:bg-emerald-900/30',iconColor: 'text-emerald-500' },
  { label: 'Expenses',        value: "$22,000", change: '+5%',   positive: false, icon: TrendingDown,iconBg:'bg-red-50 dark:bg-red-900/30',        iconColor: 'text-red-400' },
  { label: 'Net Profit',      value: "$26,250", change: '+15%',  positive: true,  icon: CreditCard, iconBg: 'bg-cyan-50 dark:bg-cyan-900/30',     iconColor: 'text-cyan-500' },
]

// ── Chart data ────────────────────────────────────
const chartData = ref([
  { name: 'Nov', revenue: 28000, expense: 12000 },
  { name: 'Dec', revenue: 35000, expense: 15000 },
  { name: 'Jan', revenue: 31000, expense: 16000 },
  { name: 'Feb', revenue: 48250, expense: 22000 },
])

const paymentMethods = computed(() => [
  { label: 'Cash',     pct: 45, color: `rgb(var(--c-secondary))` },
  { label: 'Card',     pct: 35, color: `rgba(var(--c-primary)/.7)` },
  { label: 'Transfer', pct: 20, color: '#10b981' },
])

// ── Transactions ─────────────────────────────────
const transactions = ref([])
const txSearch     = ref('')
const patientList  = ref([])
const showModal    = ref(false)
const saving       = ref(false)
let   txCounter    = ref(5)

const defaultForm = () => ({
  type: 'income', amount: '', description: '', patient_name: '',
  category: 'Consultation', method: 'Cash', status: 'Paid',
  date: new Date().toISOString().slice(0, 10)
})
const form = reactive(defaultForm())

const formattedAmount = computed(() => form.amount ? new Intl.NumberFormat('uz-UZ').format(form.amount) : '')
function onAmountInput(e) {
  const raw = e.target.value.replace(/\D/g, '')
  form.amount = raw ? parseInt(raw) : ''
  e.target.value = raw ? new Intl.NumberFormat('uz-UZ').format(parseInt(raw)) : ''
}

function fmt(v) { return new Intl.NumberFormat('uz-UZ').format(v) + ' UZS' }
function fmtShort(v) { return v >= 1000 ? (v/1000).toFixed(0) + 'K' : v }
function genTxnId() { txCounter.value++; return `TXN-${String(txCounter.value).padStart(3,'0')}` }

const summary = computed(() => ({
  income:  transactions.value.filter(t => t.type === 'income').reduce((s, t) => s + t.amount, 0),
  expense: transactions.value.filter(t => t.type === 'expense').reduce((s, t) => s + t.amount, 0),
}))

const filteredTx = computed(() => {
  const q = txSearch.value.toLowerCase()
  if (!q) return transactions.value
  return transactions.value.filter(t =>
    (t.patient_name||'').toLowerCase().includes(q) ||
    t.description.toLowerCase().includes(q) ||
    (t.txn_id||'').toLowerCase().includes(q)
  )
})

// ── Commissions ───────────────────────────────────
const commissions = ref([
  { doctor: 'Dr. Rustamov', patients: 42, revenue: 12500000, rate: 25 },
  { doctor: 'Dr. Karimov',  patients: 38, revenue: 16800000, rate: 30 },
  { doctor: 'Dr. Yusupov',  patients: 25, revenue: 8200000,  rate: 25 },
])

function openModal() { Object.assign(form, defaultForm()); showModal.value = true }
function closeModal() { showModal.value = false }

async function addTransaction() {
  if (!form.description || !form.amount) return
  saving.value = true
  await new Promise(r => setTimeout(r, 400))
  transactions.value.unshift({ ...form, amount: Number(form.amount), id: Date.now().toString(), txn_id: genTxnId() })
  saving.value = false; closeModal()
}

function deleteTransaction(id) {
  if (!confirm("O'chirishni tasdiqlaysizmi?")) return
  transactions.value = transactions.value.filter(t => t.id !== id)
}

function exportTransactions() {
  const header = ['TXN ID', 'Patient', 'Service', 'Amount', 'Method', 'Status', 'Date']
  const rows = filteredTx.value.map(t => [t.txn_id, t.patient_name||'', t.description, t.amount, t.method||'', t.status||'', t.date])
  const csv = [header, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob(['\uFEFF'+csv], { type:'text/csv;charset=utf-8;' }))
  a.download = `transactions_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

onMounted(async () => {
  try {
    const { data } = await api.get('/finance/transactions')
    transactions.value = data.map((t,i) => ({ ...t, txn_id: t.txn_id || `TXN-${String(i+1).padStart(3,'0')}`, method: t.method||'Cash', status: t.status||'Paid' }))
  } catch {
    transactions.value = [
      { id:'1', txn_id:'TXN-001', type:'income',  amount:150000,  description:'General Checkup',  patient_name:'Aziza Karimova',  method:'Card',     status:'Paid',    date:'2026-02-23', category:'Consultation' },
      { id:'2', txn_id:'TXN-002', type:'income',  amount:350000,  description:'Cardiology',       patient_name:'Bobur Aliyev',    method:'Cash',     status:'Paid',    date:'2026-02-22', category:'Consultation' },
      { id:'3', txn_id:'TXN-003', type:'income',  amount:200000,  description:'Dermatology',      patient_name:'Dilnoza Rahimova',method:'Transfer', status:'Pending', date:'2026-02-22', category:'Consultation' },
      { id:'4', txn_id:'TXN-004', type:'income',  amount:80000,   description:'Follow-up',        patient_name:'Eldor Toshmatov', method:'Card',     status:'Paid',    date:'2026-02-21', category:'Consultation' },
      { id:'5', txn_id:'TXN-005', type:'expense', amount:1200000, description:'Medical equipment', patient_name:null,              method:'Transfer', status:'Paid',    date:'2026-02-20', category:'Equipment' },
    ]
  }
  try {
    const patients = await fetchAll('/patients')
    patientList.value = patients.map(p => p.name)
  } catch {
    patientList.value = ['Aziza Karimova', 'Bobur Aliyev', 'Dilnoza Rahimova', 'Eldor Toshmatov', 'Feruza Umarova']
  }
})
</script>

<style scoped>
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>