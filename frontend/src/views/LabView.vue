<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Laboratoriya</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Buyurtmalar, natijalar va me'yor bilan solishtirish</p>
      </div>
      <button v-if="auth.can('lab:write')" class="btn-primary" @click="openNew"><Plus class="w-4 h-4" /> Yangi buyurtma</button>
    </div>

    <div class="card">
      <div :class="['p-4 border-b flex gap-3 flex-wrap', dark ? 'border-slate-800' : 'border-slate-100']">
        <select v-model="status" class="input w-auto" @change="load">
          <option value="">Barcha holat</option>
          <option value="Ordered">Kutilmoqda</option>
          <option value="Completed">Yakunlangan</option>
          <option value="Cancelled">Bekor qilingan</option>
        </select>
        <input v-model="search" class="input flex-1 min-w-48" placeholder="Bemor ismi bo'yicha filtr..." />
      </div>
      <p v-if="loading" class="p-8 text-center text-sm text-slate-400">Yuklanmoqda...</p>
      <EmptyState v-else-if="error" title="Buyurtmalarni yuklab bo'lmadi" action-label="Qayta urinish" @action="load" />
      <EmptyState v-else-if="!filtered.length" title="Buyurtma yo'q" description="Yangi laboratoriya buyurtmasini yarating" />
      <div v-else class="table-container rounded-none border-0">
        <table class="table">
          <thead><tr><th>Sana</th><th>Bemor</th><th>Shifokor</th><th>Tahlillar</th><th>Holat</th><th></th></tr></thead>
          <tbody>
            <tr v-for="o in filtered" :key="o.id">
              <td class="font-mono text-sm">{{ o.created_at.slice(0, 10) }}</td>
              <td class="font-medium">{{ o.patient_name }}</td>
              <td class="text-sm text-slate-500">{{ o.doctor }}</td>
              <td class="text-sm">
                {{ o.items.length }} ta
                <span v-if="abnormal(o)" class="badge-red ml-1">{{ abnormal(o) }} ta me'yordan tashqari</span>
              </td>
              <td><span :class="statusClass[o.status]">{{ statusLabel[o.status] }}</span><span v-if="o.approved" class="badge-blue ml-1" title="Shifokor tasdiqlagan: bemorga ko'rinadi">Tasdiqlangan</span></td>
              <td class="whitespace-nowrap">
                <button class="text-xs text-cyan-600 hover:underline mr-3" @click="openResults(o)">{{ o.status === 'Ordered' && auth.can('lab:write') ? 'Natija kiritish' : "Ko'rish" }}</button>
                <button class="text-xs text-slate-500 hover:underline" @click="openPdf(o)"><FileDown class="w-3.5 h-3.5 inline" /> PDF</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Yangi buyurtma -->
    <div v-if="showNew" class="modal-overlay" @click.self="showNew = false">
      <div :class="['w-full max-w-2xl rounded-2xl shadow-2xl p-6 max-h-[92vh] overflow-y-auto space-y-4', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Yangi laboratoriya buyurtmasi</h3>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="text-xs text-slate-400 block mb-1">Bemor *</label><input v-model="form.patient_name" class="input" placeholder="Aziza Karimova" /></div>
          <div><label class="text-xs text-slate-400 block mb-1">Shifokor *</label>
            <select v-model="form.doctor" class="input"><option value="" disabled>—</option><option v-for="d in doctors" :key="d" :value="d">{{ d }}</option></select></div>
        </div>
        <div>
          <p class="text-xs text-slate-400 mb-1.5">To'plamlar</p>
          <div class="flex flex-wrap gap-2">
            <label v-for="p in panels" :key="p.id" :class="['px-3 py-1.5 rounded-full text-xs border cursor-pointer', form.panel_ids.includes(p.id) ? 'bg-cyan-600 text-white border-cyan-600' : 'border-slate-200 text-slate-600']">
              <input v-model="form.panel_ids" type="checkbox" :value="p.id" class="hidden" />{{ p.name }}
            </label>
          </div>
        </div>
        <div>
          <p class="text-xs text-slate-400 mb-1.5">Alohida tahlillar</p>
          <input v-model="testFilter" class="input mb-2" placeholder="Tahlil qidirish..." />
          <div class="max-h-44 overflow-y-auto grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <label v-for="t in shownTests" :key="t.id" class="flex items-center gap-2"><input v-model="form.test_ids" type="checkbox" :value="t.id" /> {{ t.name }} <span class="text-xs text-slate-400">{{ t.code }}</span></label>
          </div>
        </div>
        <input v-model="form.notes" class="input" placeholder="Izoh (masalan: och qoringa)" />
        <div class="flex justify-end gap-2">
          <button class="btn-secondary" @click="showNew = false">Bekor qilish</button>
          <button class="btn-primary" :disabled="saving" @click="createOrder">Buyurtma berish</button>
        </div>
      </div>
    </div>

    <!-- Natijalar -->
    <div v-if="current" class="modal-overlay" @click.self="current = null">
      <div :class="['w-full max-w-3xl rounded-2xl shadow-2xl p-6 max-h-[92vh] overflow-y-auto space-y-4', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
        <div class="flex items-start justify-between">
          <div>
            <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ current.patient_name }}</h3>
            <p class="text-xs text-slate-400">{{ current.created_at.slice(0, 10) }} · {{ current.doctor }} · <span :class="statusClass[current.status]">{{ statusLabel[current.status] }}</span>
              <span v-if="current.approved" class="badge-blue ml-1">Tasdiqlangan: {{ current.approved_by }}, {{ current.approved_at?.slice(0, 16).replace('T', ' ') }}</span></p>
          </div>
          <button class="text-slate-400" @click="current = null"><X class="w-5 h-5" /></button>
        </div>
        <table class="w-full text-sm">
          <thead><tr class="text-left text-xs text-slate-400"><th class="py-1">Tahlil</th><th>Natija</th><th>Birlik</th><th>Me'yor</th><th>Belgi</th></tr></thead>
          <tbody>
            <tr v-for="i in current.items" :key="i.id" class="border-t" :class="dark ? 'border-slate-800' : 'border-slate-100'">
              <td class="py-1.5">{{ i.name }}</td>
              <td>
                <input v-if="canEnter || correcting" v-model="entered[i.id]" type="number" step="any" class="input w-28 py-1" />
                <span v-else :class="flagText(i.flag)">{{ i.value ?? '—' }}</span>
              </td>
              <td class="text-slate-500">{{ i.unit }}</td>
              <td class="text-slate-500 font-mono text-xs">{{ i.reference || '—' }}<span v-if="i.ref_verified === false" class="ml-1 badge-yellow text-[9px]" title="Namuna me'yor: laboratoriya tasdiqlashi kerak">namuna</span></td>
              <td><span v-if="i.value != null" :class="flagBadge[i.flag] || 'badge-slate'">{{ flagLabel[i.flag] || "Me'yor yo'q" }}</span></td>
            </tr>
          </tbody>
        </table>
        <p v-if="canEnter" class="text-xs text-slate-400">Saqlangach natijalar jins va yoshga mos me'yor bilan solishtiriladi.</p>
        <p v-if="current.approved && !correcting" class="text-xs text-slate-400">Tasdiqlangan natija tahrirlanmaydi. O'zgartirish faqat sabab ko'rsatilgan tuzatish yozuvi orqali.</p>
        <div v-if="correcting" class="space-y-2">
          <textarea v-model="reason" rows="2" class="input" placeholder="Tuzatish sababi (kamida 5 belgi, majburiy)"></textarea>
        </div>
        <div v-if="current.corrections?.length" class="space-y-1">
          <p class="text-xs font-semibold text-slate-500">Tuzatishlar tarixi</p>
          <div v-for="c in current.corrections" :key="c.id" class="text-xs text-slate-500 border-l-2 border-amber-400 pl-2">
            <b>{{ c.test_name }}</b>: {{ c.old_value ?? '—' }} → {{ c.new_value }} · {{ c.corrected_by }}, {{ c.corrected_at.slice(0, 16).replace('T', ' ') }} · {{ c.reason }}
          </div>
        </div>
        <div class="flex justify-between gap-2 flex-wrap">
          <button v-if="canCancel" class="text-sm text-red-500 hover:underline" @click="cancelOrder">Buyurtmani bekor qilish</button>
          <span class="flex-1"></span>
          <button class="btn-secondary" @click="openPdf(current)"><FileDown class="w-4 h-4" /> PDF</button>
          <button v-if="canEnter" class="btn-primary" :disabled="saving" @click="saveResults">Natijalarni saqlash</button>
          <button v-if="canApprove" class="btn-primary" :disabled="saving" @click="approveOrder">Tasdiqlash</button>
          <button v-if="canCorrect && !correcting" class="btn-secondary" @click="correcting = true">Tuzatish kiritish</button>
          <button v-if="correcting" class="btn-secondary" @click="correcting = false">Bekor qilish</button>
          <button v-if="correcting" class="btn-primary" :disabled="saving" @click="saveCorrection">Tuzatishni saqlash</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, X, FileDown } from 'lucide-vue-next'
import api, { fetchAll } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast()
const theme = useThemeStore()
const auth = useAuthStore()
const dark = computed(() => theme.isDark)

const statusLabel = { Ordered: 'Kutilmoqda', Completed: 'Yakunlangan', Cancelled: 'Bekor qilingan' }
const statusClass = { Ordered: 'badge-yellow', Completed: 'badge-green', Cancelled: 'badge-slate' }
const flagLabel = { Low: 'Past', Normal: "Me'yorda", High: 'Yuqori' }
const flagBadge = { Low: 'badge-blue', Normal: 'badge-green', High: 'badge-red' }
const flagText = f => (f === 'Low' || f === 'High' ? 'font-semibold text-red-600' : '')

const orders = ref([]), loading = ref(true), error = ref(false), status = ref(''), search = ref('')
const panels = ref([]), tests = ref([]), doctors = ref([])
const filtered = computed(() => orders.value.filter(o => !search.value || o.patient_name.toLowerCase().includes(search.value.toLowerCase())))
const abnormal = o => o.items.filter(i => i.flag === 'Low' || i.flag === 'High').length

async function load() {
  loading.value = true
  error.value = false
  try {
    orders.value = (await api.get('/lab/orders', { params: status.value ? { status: status.value } : {} })).data
  } catch (e) {
    orders.value = []
    error.value = true
    toast.error(e, "Buyurtmalarni yuklab bo'lmadi")
  } finally { loading.value = false }
}

// Yangi buyurtma
const showNew = ref(false), saving = ref(false), testFilter = ref('')
const form = reactive({ patient_name: '', doctor: '', panel_ids: [], test_ids: [], notes: '' })
const shownTests = computed(() => tests.value.filter(t => !testFilter.value || (t.name + t.code).toLowerCase().includes(testFilter.value.toLowerCase())))
function openNew() { Object.assign(form, { patient_name: '', doctor: '', panel_ids: [], test_ids: [], notes: '' }); showNew.value = true }
async function createOrder() {
  saving.value = true
  try {
    const found = await fetchAll('/patients', { search: form.patient_name })
    const patient = found.find(p => p.name.toLowerCase() === form.patient_name.trim().toLowerCase())
    if (!patient) { toast.error(`"${form.patient_name}" nomli bemor topilmadi`); return }
    await api.post('/lab/orders', { patient_id: patient.id, doctor: form.doctor, panel_ids: form.panel_ids, test_ids: form.test_ids, notes: form.notes || null })
    toast.success('Buyurtma berildi')
    showNew.value = false
    await load()
  } catch (e) { toast.error(e, "Buyurtma berib bo'lmadi") } finally { saving.value = false }
}

// Natijalar
const current = ref(null), entered = reactive({})
const canEnter = computed(() => current.value && current.value.status !== 'Cancelled' && !current.value.approved && auth.can('lab:write'))
const canApprove = computed(() => current.value?.status === 'Completed' && !current.value.approved && auth.can('lab:approve'))
const canCorrect = computed(() => current.value?.approved && auth.can('lab:approve'))
const correcting = ref(false), reason = ref('')
const canCancel = computed(() => current.value?.status === 'Ordered' && auth.can('lab:write') && current.value.items.every(i => i.value == null))
function openResults(o) {
  current.value = o
  correcting.value = false
  reason.value = ''
  Object.keys(entered).forEach(k => delete entered[k])
  o.items.forEach(i => { entered[i.id] = i.value ?? '' })
}
async function saveResults() {
  const results = current.value.items.filter(i => entered[i.id] !== '' && entered[i.id] !== null && Number(entered[i.id]) !== i.value)
    .map(i => ({ item_id: i.id, value: Number(entered[i.id]) }))
  if (!results.length) { toast.success("O'zgarish yo'q"); return }
  saving.value = true
  try {
    const { data } = await api.put(`/lab/orders/${current.value.id}/results`, { results })
    toast.success('Natijalar saqlandi')
    const idx = orders.value.findIndex(o => o.id === data.id)
    if (idx >= 0) orders.value[idx] = data
    openResults(data)
  } catch (e) { toast.error(e, "Natijalarni saqlab bo'lmadi") } finally { saving.value = false }
}
function replaceOrder(data) {
  const idx = orders.value.findIndex(o => o.id === data.id)
  if (idx >= 0) orders.value[idx] = data
  openResults(data)
}
async function approveOrder() {
  saving.value = true
  try {
    replaceOrder((await api.post(`/lab/orders/${current.value.id}/approve`)).data)
    toast.success('Natija tasdiqlandi: bemorga ko\'rinadi')
  } catch (e) { toast.error(e, "Tasdiqlab bo'lmadi") } finally { saving.value = false }
}
async function saveCorrection() {
  const results = current.value.items.filter(i => entered[i.id] !== '' && entered[i.id] !== null && Number(entered[i.id]) !== i.value)
    .map(i => ({ item_id: i.id, value: Number(entered[i.id]) }))
  if (!results.length) { toast.success("O'zgarish yo'q"); return }
  if (reason.value.trim().length < 5) { toast.error('Tuzatish sababini yozing (kamida 5 belgi)'); return }
  saving.value = true
  try {
    replaceOrder((await api.post(`/lab/orders/${current.value.id}/corrections`, { reason: reason.value.trim(), results })).data)
    toast.success('Tuzatish yozuvi saqlandi')
  } catch (e) { toast.error(e, "Tuzatishni saqlab bo'lmadi") } finally { saving.value = false }
}
async function cancelOrder() {
  try {
    await api.post(`/lab/orders/${current.value.id}/cancel`)
    toast.success('Buyurtma bekor qilindi')
    current.value = null
    await load()
  } catch (e) { toast.error(e, "Bekor qilib bo'lmadi") }
}
async function openPdf(o) {
  try {
    const { data } = await api.get(`/lab/orders/${o.id}/pdf`, { responseType: 'blob' })
    window.open(URL.createObjectURL(data), '_blank')
  } catch (e) { toast.error(e, "PDF ochib bo'lmadi") }
}

onMounted(async () => {
  load()
  try {
    const [p, t] = await Promise.all([api.get('/lab/panels'), api.get('/lab/tests')])
    panels.value = p.data
    tests.value = t.data
  } catch (e) { toast.error(e, "Tahlil katalogini yuklab bo'lmadi") }
  try { doctors.value = (await api.get('/staff', { params: { role: 'Doctor' } })).data.map(s => s.name) } catch { doctors.value = [] }
})
</script>
