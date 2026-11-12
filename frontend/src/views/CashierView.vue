<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Kassa</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Smena, hisob-fakturalar, to'lov va qaytarish</p>
      </div>
      <button v-if="auth.can('finance:write')" class="btn-primary" @click="openCreate"><Plus class="w-4 h-4" /> Yangi hisob-faktura</button>
    </div>

    <!-- Smena -->
    <div class="card p-5">
      <p v-if="shiftLoading" class="text-sm text-slate-400">Yuklanmoqda...</p>
      <div v-else-if="shift" class="space-y-3">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="badge-green">Smena ochiq</span>
          <span class="text-sm text-slate-500">{{ shift.cashier }} · {{ shift.opened_at.slice(0, 16).replace('T', ' ') }}</span>
          <span class="flex-1"></span>
          <button class="btn-secondary text-sm" @click="openShiftPdf(shift)"><FileDown class="w-4 h-4" /> X-hisobot PDF</button>
          <button class="btn-primary text-sm" @click="showClose = true">Smenani yopish</button>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div><p class="text-xs text-slate-400">Boshlang'ich naqd</p><p class="font-mono font-semibold">{{ fmt(shift.opening_cash) }}</p></div>
          <div><p class="text-xs text-slate-400">Naqd tushum / qaytarish</p><p class="font-mono">{{ fmt(shift.cash.payments_total) }} / {{ fmt(shift.cash.refunds_total) }}</p></div>
          <div><p class="text-xs text-slate-400">Karta tushum / qaytarish</p><p class="font-mono">{{ fmt(shift.card.payments_total) }} / {{ fmt(shift.card.refunds_total) }}</p></div>
          <div><p class="text-xs text-slate-400">Kassada kutilgan naqd</p><p class="font-mono font-semibold text-cyan-600">{{ fmt(shift.expected_cash) }}</p></div>
        </div>
        <p v-if="shift.receipts_missing" class="text-sm text-amber-600">Diqqat: {{ shift.receipts_missing }} ta to'lovning fiskal cheki berilmagan (hisob-faktura ichida "Chekni qayta berish").</p>
      </div>
      <div v-else class="flex items-center gap-3 flex-wrap">
        <span class="badge-slate">Smena yopiq</span>
        <span class="text-sm text-slate-500">Naqd/karta to'lovi qabul qilish uchun smenani oching.</span>
        <span class="flex-1"></span>
        <button v-if="auth.can('finance:write')" class="btn-primary text-sm" @click="showOpen = true">Smenani ochish</button>
      </div>
      <div v-if="lastZ" class="mt-4 p-3 rounded-xl text-sm" :class="dark ? 'bg-slate-800' : 'bg-slate-50'">
        {{ lastZ.z_number }} yopildi. Kutilgan {{ fmt(lastZ.expected_cash) }}, sanalgan {{ fmt(lastZ.counted_cash) }},
        <span :class="lastZ.difference ? 'text-red-500 font-semibold' : 'text-emerald-600'">farq {{ fmt(lastZ.difference) }}</span>.
        <button class="underline ml-2" @click="openShiftPdf(lastZ)">Z-hisobot PDF</button>
      </div>
    </div>

    <!-- Hisob-fakturalar -->
    <div class="card">
      <div :class="['p-4 border-b flex gap-3 flex-wrap', dark ? 'border-slate-800' : 'border-slate-100']">
        <select v-model="status" class="input w-auto" @change="loadInvoices">
          <option value="">Barcha holat</option>
          <option v-for="(label, k) in statusLabel" :key="k" :value="k">{{ label }}</option>
        </select>
        <input v-model="numberFilter" class="input flex-1 min-w-40" placeholder="Raqam yoki bemor..." />
      </div>
      <p v-if="loading" class="p-8 text-center text-sm text-slate-400">Yuklanmoqda...</p>
      <EmptyState v-else-if="error" title="Hisob-fakturalarni yuklab bo'lmadi" action-label="Qayta urinish" @action="loadInvoices" />
      <EmptyState v-else-if="!shown.length" title="Hisob-faktura yo'q" description="Yangi hisob-faktura yarating" />
      <div v-else class="table-container rounded-none border-0">
        <table class="table">
          <thead><tr><th>Raqam</th><th>Bemor</th><th class="text-right">Jami (UZS)</th><th class="text-right">To'langan</th><th class="text-right">Qoldiq</th><th>Holat</th><th></th></tr></thead>
          <tbody>
            <tr v-for="i in shown" :key="i.id">
              <td class="font-mono text-sm">{{ i.number }}</td>
              <td class="font-medium">{{ i.patient_name }}</td>
              <td class="text-right font-mono">{{ fmt(i.total) }}</td>
              <td class="text-right font-mono">{{ fmt(i.paid_amount - i.refunded_amount) }}</td>
              <td class="text-right font-mono" :class="i.balance > 0 ? 'text-amber-600' : ''">{{ fmt(i.balance) }}</td>
              <td><span :class="statusClass[i.status]">{{ statusLabel[i.status] }}</span></td>
              <td><button class="text-xs text-cyan-600 hover:underline" @click="openDetail(i)">Ochish</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Smenani ochish -->
    <div v-if="showOpen" class="modal-overlay" @click.self="showOpen = false">
      <div :class="modalClass('max-w-sm')">
        <h3 :class="titleClass">Smenani ochish</h3>
        <div><label class="text-xs text-slate-400 block mb-1">Kassadagi boshlang'ich naqd (UZS)</label><input v-model.number="openCash" type="number" min="0" step="0.01" class="input" /></div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="showOpen = false">Bekor qilish</button><button class="btn-primary" :disabled="busy" @click="openShift">Ochish</button></div>
      </div>
    </div>

    <!-- Smenani yopish -->
    <div v-if="showClose" class="modal-overlay" @click.self="showClose = false">
      <div :class="modalClass('max-w-sm')">
        <h3 :class="titleClass">Smenani yopish (Z-hisobot)</h3>
        <p class="text-sm text-slate-500">Kutilgan naqd: <b class="font-mono">{{ fmt(shift.expected_cash) }}</b>. Kassadagi naqdni sanab kiriting.</p>
        <div><label class="text-xs text-slate-400 block mb-1">Sanalgan naqd (UZS)</label><input v-model.number="countedCash" type="number" min="0" step="0.01" class="input" /></div>
        <p v-if="countedCash !== ''" class="text-sm" :class="countedCash - shift.expected_cash ? 'text-amber-600' : 'text-emerald-600'">Farq: {{ fmt(countedCash - shift.expected_cash) }}</p>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="showClose = false">Bekor qilish</button><button class="btn-primary" :disabled="busy || countedCash === ''" @click="closeShift">Yopish</button></div>
      </div>
    </div>

    <!-- Yangi hisob-faktura -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div :class="modalClass('max-w-2xl')">
        <h3 :class="titleClass">Yangi hisob-faktura</h3>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="text-xs text-slate-400 block mb-1">Bemor *</label><input v-model="form.patient_name" class="input" placeholder="Aziza Karimova" /></div>
          <div><label class="text-xs text-slate-400 block mb-1">Shifokor (ijrochi)</label>
            <select v-model="form.doctor_id" class="input"><option value="">—</option><option v-for="d in doctors" :key="d.id" :value="d.id">{{ d.name }}</option></select></div>
        </div>
        <div class="space-y-2">
          <div v-for="(l, i) in form.lines" :key="i" class="grid grid-cols-12 gap-2 items-center">
            <select v-model="l.service_id" class="input col-span-6"><option value="" disabled>Xizmat tanlang</option><option v-for="s in services" :key="s.id" :value="s.id">{{ s.name }} — {{ fmt(s.price) }}</option></select>
            <input v-model.number="l.quantity" type="number" min="1" max="999" class="input col-span-2" />
            <input v-if="canDiscount" v-model.number="l.discount_percent" type="number" min="0" max="100" step="0.01" class="input col-span-3" placeholder="chegirma %" />
            <button class="text-red-500 col-span-1" @click="form.lines.splice(i, 1)"><Trash2 class="w-4 h-4" /></button>
          </div>
          <button class="text-xs text-cyan-600" @click="form.lines.push({ service_id: '', quantity: 1, discount_percent: null })"><Plus class="w-3.5 h-3.5 inline" /> Xizmat qo'shish</button>
          <p v-if="!services.length" class="text-xs text-amber-600">Sotiladigan xizmat yo'q: Sozlamalar > Narxnoma da MXIK, package_code va QQS to'ldiring.</p>
        </div>
        <div v-if="canDiscount" class="grid grid-cols-3 gap-3">
          <div><label class="text-xs text-slate-400 block mb-1">Umumiy chegirma %</label><input v-model.number="form.discount_percent" type="number" min="0" max="100" step="0.01" class="input" /></div>
          <div class="col-span-2"><label class="text-xs text-slate-400 block mb-1">Chegirma sababi</label><input v-model="form.discount_reason" class="input" /></div>
        </div>
        <p class="text-sm text-slate-500">Taxminiy summa (chegirmasiz): <b class="font-mono">{{ fmt(estimate) }}</b> UZS. Aniq summa server hisoblaydi.</p>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="showCreate = false">Bekor qilish</button><button class="btn-primary" :disabled="busy" @click="createInvoice">Yaratish va chiqarish</button></div>
      </div>
    </div>

    <!-- Hisob-faktura tafsiloti -->
    <div v-if="detail" class="modal-overlay" @click.self="detail = null">
      <div :class="modalClass('max-w-3xl')">
        <div class="flex items-start justify-between">
          <div>
            <h3 :class="titleClass">{{ detail.number }} · {{ detail.patient_name }}</h3>
            <p class="text-xs text-slate-400"><span :class="statusClass[detail.status]">{{ statusLabel[detail.status] }}</span> · {{ detail.doctor || 'shifokorsiz' }}</p>
          </div>
          <button class="text-slate-400" @click="detail = null"><X class="w-5 h-5" /></button>
        </div>
        <table class="w-full text-sm">
          <thead><tr class="text-left text-xs text-slate-400"><th class="py-1">Xizmat</th><th>Soni</th><th class="text-right">Narx</th><th class="text-right">Chegirma</th><th class="text-right">Summa</th></tr></thead>
          <tbody>
            <tr v-for="l in detail.lines" :key="l.id" class="border-t" :class="dark ? 'border-slate-800' : 'border-slate-100'">
              <td class="py-1.5">{{ l.name }}<span class="block text-[10px] text-slate-400 font-mono">MXIK {{ l.mxik }} · QQS {{ l.vat_percent }}%</span></td>
              <td>{{ l.quantity }}</td><td class="text-right font-mono">{{ fmt(l.unit_price) }}</td>
              <td class="text-right font-mono">{{ fmt(l.line_discount + l.invoice_discount_share) }}</td><td class="text-right font-mono">{{ fmt(l.net_total) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="text-right text-sm space-y-0.5">
          <p>Chegirma: <span class="font-mono">{{ fmt(detail.discount_total) }}</span> <span v-if="detail.discount_reason" class="text-slate-400">({{ detail.discount_reason }})</span></p>
          <p>QQS: <span class="font-mono">{{ fmt(detail.vat_total) }}</span></p>
          <p class="font-semibold">Jami: <span class="font-mono">{{ fmt(detail.total) }}</span> · Qoldiq: <span class="font-mono text-amber-600">{{ fmt(detail.balance) }}</span></p>
        </div>

        <div>
          <h4 class="text-sm font-semibold mb-2" :class="dark ? 'text-slate-200' : 'text-slate-800'">To'lovlar</h4>
          <p v-if="!payments.length" class="text-xs text-slate-400">To'lov yo'q</p>
          <ul v-else class="space-y-2">
            <li v-for="p in payments" :key="p.id" class="text-sm border rounded-xl p-3" :class="dark ? 'border-slate-800' : 'border-slate-200'">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="badge-blue">{{ p.method }}</span><span class="font-mono font-semibold">{{ fmt(p.amount) }}</span>
                <span :class="payClass[p.status]">{{ payLabel[p.status] }}</span>
                <span v-if="p.refunded_amount" class="badge-yellow">qaytarilgan {{ fmt(p.refunded_amount) }}</span>
                <span class="flex-1"></span>
                <span v-if="p.receipt_id" class="text-xs font-mono text-slate-500" title="Fiskal chek ID">chek {{ p.receipt_id }}</span>
                <button v-else-if="p.status === 'Paid'" class="text-xs text-amber-600 underline" @click="retryReceipt(p)">Chekni qayta berish</button>
              </div>
              <div v-if="p.status === 'Pending' && p.checkout_url" class="mt-2 text-xs">
                To'lov havolasi: <a :href="p.checkout_url" target="_blank" class="text-cyan-600 underline break-all">{{ p.checkout_url }}</a>
                <button class="ml-2 underline" @click="copy(p.checkout_url)">Nusxalash</button>
              </div>
              <div v-if="p.status === 'Pending' && !p.provider_txn_id" class="mt-1"><button class="text-xs text-red-500 underline" @click="cancelPending(p)">Bekor qilish</button></div>
              <div v-if="canRefund(p)" class="mt-2 flex items-center gap-2 flex-wrap">
                <input v-model="refund[p.id].amount" type="number" min="0" step="0.01" class="input w-32 py-1 text-xs" :placeholder="'summa (' + fmt(p.amount - p.refunded_amount) + ')'" />
                <input v-model="refund[p.id].reason" class="input flex-1 py-1 text-xs" placeholder="Qaytarish sababi" />
                <button class="text-xs text-red-500 underline" :disabled="busy || (refund[p.id].reason || '').length < 3" @click="doRefund(p)">Qaytarish</button>
              </div>
            </li>
          </ul>
        </div>

        <div v-if="auth.can('finance:write') && ['Issued', 'PartiallyPaid'].includes(detail.status)" class="flex items-end gap-2 flex-wrap pt-1">
          <div><label class="text-xs text-slate-400 block mb-1">Usul</label>
            <select v-model="pay.method" class="input"><option>Cash</option><option>Card</option><option>Payme</option><option>Click</option></select></div>
          <div><label class="text-xs text-slate-400 block mb-1">Summa (bo'sh: qoldiq)</label><input v-model.number="pay.amount" type="number" min="0" step="0.01" class="input w-40" :placeholder="String(detail.balance)" /></div>
          <button class="btn-primary" :disabled="busy" @click="doPay">To'lov qabul qilish</button>
          <button v-if="!payments.some(p => ['Paid', 'Pending'].includes(p.status))" class="text-sm text-red-500 underline ml-auto" @click="doCancelInvoice">Hisob-fakturani bekor qilish</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, X, Trash2, FileDown } from 'lucide-vue-next'
import api, { fetchAll } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast()
const theme = useThemeStore()
const auth = useAuthStore()
const dark = computed(() => theme.isDark)
const fmt = v => new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 2 }).format(v ?? 0)
const modalClass = w => ['w-full rounded-2xl shadow-2xl p-6 max-h-[92vh] overflow-y-auto space-y-4', w, dark.value ? 'bg-slate-900 border border-slate-800' : 'bg-white']
const titleClass = computed(() => ['font-heading font-semibold', dark.value ? 'text-white' : 'text-slate-900'])

const statusLabel = { Draft: 'Qoralama', Issued: 'Chiqarilgan', PartiallyPaid: 'Qisman to\'langan', Paid: "To'langan", Cancelled: 'Bekor qilingan' }
const statusClass = { Draft: 'badge-slate', Issued: 'badge-yellow', PartiallyPaid: 'badge-blue', Paid: 'badge-green', Cancelled: 'badge-slate' }
const payLabel = { Pending: 'Kutilmoqda', Paid: "To'langan", Failed: 'Xato', Cancelled: 'Bekor' }
const payClass = { Pending: 'badge-yellow', Paid: 'badge-green', Failed: 'badge-red', Cancelled: 'badge-slate' }

// Smena
const shift = ref(null), shiftLoading = ref(true), lastZ = ref(null), busy = ref(false)
const showOpen = ref(false), showClose = ref(false), openCash = ref(0), countedCash = ref('')
async function loadShift() {
  shiftLoading.value = true
  try { shift.value = (await api.get('/cash-shifts/current')).data } catch (e) {
    if (e?.response?.status !== 403) toast.error(e, "Smenani yuklab bo'lmadi")
    shift.value = null
  } finally { shiftLoading.value = false }
}
async function openShift() {
  busy.value = true
  try { await api.post('/cash-shifts/open', { opening_cash: openCash.value || 0 }); showOpen.value = false; lastZ.value = null; toast.success('Smena ochildi'); await loadShift() }
  catch (e) { toast.error(e, "Smenani ochib bo'lmadi") } finally { busy.value = false }
}
async function closeShift() {
  busy.value = true
  try {
    lastZ.value = (await api.post(`/cash-shifts/${shift.value.shift_id}/close`, { counted_cash: countedCash.value })).data
    showClose.value = false; countedCash.value = ''
    toast.success('Smena yopildi')
    await loadShift()
  } catch (e) { toast.error(e, "Smenani yopib bo'lmadi") } finally { busy.value = false }
}
async function openShiftPdf(s) {
  try { window.open(URL.createObjectURL((await api.get(`/cash-shifts/${s.shift_id}/z-report/pdf`, { responseType: 'blob' })).data), '_blank') }
  catch (e) { toast.error(e, "PDF ochib bo'lmadi") }
}

// Ro'yxat
const invoices = ref([]), loading = ref(true), error = ref(false), status = ref(''), numberFilter = ref('')
const shown = computed(() => invoices.value.filter(i => !numberFilter.value || (i.number + i.patient_name).toLowerCase().includes(numberFilter.value.toLowerCase())))
async function loadInvoices() {
  loading.value = true; error.value = false
  try { invoices.value = (await api.get('/invoices', { params: { limit: 100, ...(status.value ? { status: status.value } : {}) } })).data }
  catch (e) { invoices.value = []; error.value = true; toast.error(e, "Hisob-fakturalarni yuklab bo'lmadi") } finally { loading.value = false }
}

// Yangi hisob-faktura
const showCreate = ref(false), services = ref([]), doctors = ref([])
const canDiscount = computed(() => auth.can('finance:discount'))
const form = reactive({ patient_name: '', doctor_id: '', lines: [], discount_percent: null, discount_reason: '' })
const estimate = computed(() => form.lines.reduce((sum, l) => sum + (services.value.find(s => s.id === l.service_id)?.price || 0) * (l.quantity || 0), 0))
function openCreate() { Object.assign(form, { patient_name: '', doctor_id: '', lines: [{ service_id: '', quantity: 1, discount_percent: null }], discount_percent: null, discount_reason: '' }); showCreate.value = true }
async function createInvoice() {
  busy.value = true
  try {
    const found = await fetchAll('/patients', { search: form.patient_name })
    const patient = found.find(p => p.name.toLowerCase() === form.patient_name.trim().toLowerCase())
    if (!patient) { toast.error(`"${form.patient_name}" nomli bemor topilmadi`); return }
    const lines = form.lines.filter(l => l.service_id).map(l => ({ service_id: l.service_id, quantity: l.quantity || 1, ...(l.discount_percent ? { discount_percent: l.discount_percent } : {}) }))
    await api.post('/invoices', { patient_id: patient.id, doctor_id: form.doctor_id || null, lines, issue: true,
      ...(form.discount_percent ? { discount_percent: form.discount_percent } : {}), discount_reason: form.discount_reason || null })
    toast.success('Hisob-faktura chiqarildi')
    showCreate.value = false
    await loadInvoices()
  } catch (e) { toast.error(e, "Hisob-faktura yaratib bo'lmadi") } finally { busy.value = false }
}

// Tafsilot, to'lov, qaytarish
const detail = ref(null), payments = ref([]), pay = reactive({ method: 'Cash', amount: '' }), refund = reactive({})
const canRefund = p => auth.can('finance:refund') && p.status === 'Paid' && ['Cash', 'Card'].includes(p.method) && p.amount - p.refunded_amount > 0
async function openDetail(i) {
  try {
    detail.value = (await api.get(`/invoices/${i.id}`)).data
    payments.value = (await api.get(`/invoices/${i.id}/payments`)).data
    payments.value.forEach(p => { refund[p.id] = refund[p.id] || { amount: '', reason: '' } })
    Object.assign(pay, { method: 'Cash', amount: '' })
  } catch (e) { toast.error(e, "Hisob-fakturani yuklab bo'lmadi") }
}
async function refreshDetail() { if (detail.value) await openDetail(detail.value); await Promise.all([loadInvoices(), loadShift()]) }
async function doPay() {
  busy.value = true
  try {
    const { data } = await api.post(`/invoices/${detail.value.id}/payments`, { method: pay.method, ...(pay.amount ? { amount: pay.amount } : {}) })
    toast.success(data.status === 'Pending' ? "To'lov havolasi yaratildi" : `To'lov qabul qilindi, chek ${data.receipt_id}`)
    await refreshDetail()
  } catch (e) { toast.error(e, "To'lovni qabul qilib bo'lmadi") } finally { busy.value = false }
}
async function doRefund(p) {
  busy.value = true
  try {
    await api.post(`/payments/${p.id}/refunds`, { reason: refund[p.id].reason, ...(refund[p.id].amount ? { amount: refund[p.id].amount } : {}) })
    toast.success('Qaytarildi'); refund[p.id] = { amount: '', reason: '' }
    await refreshDetail()
  } catch (e) { toast.error(e, "Qaytarib bo'lmadi") } finally { busy.value = false }
}
async function retryReceipt(p) { try { await api.post(`/payments/${p.id}/receipt`); toast.success('Chek berildi'); await refreshDetail() } catch (e) { toast.error(e, "Chek berib bo'lmadi") } }
async function cancelPending(p) { try { await api.post(`/payments/${p.id}/cancel`); toast.success('Bekor qilindi'); await refreshDetail() } catch (e) { toast.error(e, "Bekor qilib bo'lmadi") } }
async function doCancelInvoice() {
  try { await api.post(`/invoices/${detail.value.id}/cancel`, { reason: 'Kassir tomonidan bekor qilindi' }); toast.success('Hisob-faktura bekor qilindi'); detail.value = null; await loadInvoices() }
  catch (e) { toast.error(e, "Bekor qilib bo'lmadi") }
}
async function copy(text) { try { await navigator.clipboard.writeText(text); toast.success('Nusxalandi') } catch { toast.error("Nusxalab bo'lmadi") } }

onMounted(async () => {
  loadShift(); loadInvoices()
  try { services.value = (await api.get('/services', { params: { sellable: true } })).data } catch { services.value = [] }
  try { doctors.value = (await api.get('/staff', { params: { role: 'Doctor' } })).data } catch { doctors.value = [] }
})
</script>
