<template>
  <div class="card p-5 space-y-4 max-w-5xl">
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <div>
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Narxnoma</h3>
        <p class="text-xs text-slate-400 mt-0.5">Narx QQS bilan. MXIK (IKPU, 17 raqam), package_code va QQS to'liq bo'lmasa xizmat saqlanadi, lekin sotib bo'lmaydi.</p>
      </div>
      <button v-if="auth.can('services:write')" class="btn-primary text-sm" @click="openNew"><Plus class="w-4 h-4" /> Yangi xizmat</button>
    </div>
    <div class="flex gap-2 flex-wrap">
      <input v-model="search" class="input flex-1 min-w-48" placeholder="Xizmat qidirish..." />
      <select v-model="onlyState" class="input w-auto"><option value="">Barchasi</option><option value="sellable">Sotiladigan</option><option value="incomplete">Kodi to'liq emas</option></select>
    </div>
    <p v-if="error" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <EmptyState v-else-if="!shown.length" title="Xizmat yo'q" description="Birinchi xizmatni qo'shing" />
    <div v-else class="table-container rounded-none border-0">
      <table class="table">
        <thead><tr><th>Xizmat</th><th>Kategoriya</th><th class="text-right" title="Faol filialda amal qiladigan narx">Narx (UZS)</th><th>MXIK</th><th>Qadoq</th><th>QQS</th><th class="text-right" title="Sarf normasi x ombor narxi">Tannarx</th><th class="text-right">Foyda</th><th>Holat</th><th></th></tr></thead>
        <tbody>
          <tr v-for="s in shown" :key="s.id" :class="s.is_active ? '' : 'opacity-60'">
            <td class="font-medium">{{ s.name }}</td>
            <td class="text-sm text-slate-500">{{ s.category || '—' }}</td>
            <td class="text-right font-mono" data-testid="svc-price">{{ fmt(s.effective_price ?? s.price) }}<span v-if="s.branch_price != null" class="block text-[10px] text-cyan-600 font-sans" :title="'Asosiy narx ' + fmt(s.price)">filial narxi</span></td>
            <td class="font-mono text-xs">{{ s.mxik || '—' }}</td>
            <td class="font-mono text-xs">{{ s.package_code || '—' }}</td>
            <td class="text-sm">{{ s.vat_percent != null ? s.vat_percent + '%' : '—' }}</td>
            <td class="text-right font-mono text-sm" data-testid="svc-cost">
              <template v-if="costs[s.id]">{{ fmt(costs[s.id].cost) }}<span v-if="!costs[s.id].complete" class="badge-yellow ml-1" :title="'Narxi noma\'lum: ' + costs[s.id].missing.join(', ')">?</span></template>
              <span v-else class="text-slate-300">—</span>
            </td>
            <td class="text-right text-sm" :class="costs[s.id] && costs[s.id].margin < 0 ? 'text-red-600' : 'text-emerald-600'">
              <template v-if="costs[s.id] && costs[s.id].margin_percent != null">{{ costs[s.id].margin_percent }}%</template>
            </td>
            <td>
              <span v-if="!s.is_active" class="badge-slate">Nofaol</span>
              <span v-else-if="s.sellable" class="badge-green">Sotiladi</span>
              <span v-else class="badge-yellow" :title="'Yetishmaydi: ' + s.missing.join(', ')">Kod to'liq emas</span>
            </td>
            <td class="whitespace-nowrap">
              <button v-if="auth.can('services:write') && auth.can('warehouse:read')" class="text-xs text-cyan-600 hover:underline mr-2" data-testid="svc-norms" @click="openNorms(s)">Sarf normasi</button>
              <button v-if="auth.can('services:write')" class="text-slate-400 hover:text-cyan-600" title="Tahrirlash" @click="openEdit(s)"><Pencil class="w-4 h-4" /></button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="norms.service" class="modal-overlay" @click.self="norms.service = null">
      <div :class="['w-full max-w-2xl rounded-2xl shadow-2xl p-6 space-y-3 max-h-[92vh] overflow-y-auto', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Sarf normasi: {{ norms.service.name }}</h3>
        <p class="text-xs text-slate-400">Bir marta xizmat ko'rsatishga ketadigan materiallar. Hisob-faktura to'liq to'langanda ombordan FEFO bo'yicha yoziladi; tannarx ombor narxidan avtomatik hisoblanadi.</p>
        <div v-for="(l, i) in norms.lines" :key="i" class="grid grid-cols-12 gap-2">
          <select v-model="l.item_id" class="input col-span-8" data-testid="norm-item"><option value="" disabled>Material</option><option v-for="it in norms.items" :key="it.id" :value="it.id">{{ it.name }} ({{ it.unit }})</option></select>
          <input v-model.number="l.qty" type="number" min="0" step="0.001" class="input col-span-3" placeholder="Miqdor" data-testid="norm-qty" />
          <button class="text-red-500 col-span-1" @click="norms.lines.splice(i, 1)">×</button>
        </div>
        <button class="text-xs text-cyan-600" data-testid="norm-add" @click="norms.lines.push({ item_id: '', qty: null })"><Plus class="w-3.5 h-3.5 inline" /> Material qo'shish</button>
        <div v-if="norms.cost" class="rounded-xl p-3 text-sm space-y-1" :class="dark ? 'bg-slate-800' : 'bg-slate-50'" data-testid="norm-cost">
          <p v-for="m in norms.cost.materials" :key="m.item_id" class="text-xs text-slate-500">{{ m.item }}: {{ m.qty }} {{ m.unit }} × {{ m.unit_cost != null ? fmt(m.unit_cost) : 'narx yo\'q' }} = {{ m.cost != null ? fmt(m.cost) : '—' }}
            <span class="text-slate-400">({{ ({ stock: 'ombor o\'rtachasi', last_receipt: 'oxirgi kirim', unknown: 'kirim yo\'q' })[m.source] }})</span></p>
          <p class="font-semibold">Tannarx {{ fmt(norms.cost.cost) }} · QQS'siz narx {{ fmt(norms.cost.net_price) }} · foyda {{ fmt(norms.cost.margin) }}<span v-if="norms.cost.margin_percent != null"> ({{ norms.cost.margin_percent }}%)</span></p>
          <p v-if="!norms.cost.complete && norms.cost.materials.length" class="text-xs text-amber-600">Narxi noma'lum: {{ norms.cost.missing.join(', ') }} (hali kirim yo'q)</p>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="norms.service = null">Yopish</button><button class="btn-primary" :disabled="norms.saving" data-testid="norm-save" @click="saveNorms">Saqlash</button></div>
      </div>
    </div>

    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div :class="['w-full max-w-lg rounded-2xl shadow-2xl p-6 space-y-3 max-h-[92vh] overflow-y-auto', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ editingId ? 'Xizmatni tahrirlash' : 'Yangi xizmat' }}</h3>
        <div><label class="text-xs text-slate-400 block mb-1">Nomi *</label><input v-model="form.name" class="input" maxlength="200" /></div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="text-xs text-slate-400 block mb-1">Narx (UZS, QQS bilan) *</label><input v-model.number="form.price" type="number" min="0" step="0.01" class="input" /></div>
          <div><label class="text-xs text-slate-400 block mb-1">Kategoriya</label>
            <select v-model="form.category_id" class="input"><option value="">—</option><option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option></select></div>
        </div>
        <div v-if="editingId && auth.can('services:write')" class="rounded-xl p-3 space-y-2" :class="dark ? 'bg-slate-800' : 'bg-slate-50'" data-testid="branch-price-box">
          <label class="text-xs text-slate-400 block">Faol filial narxi (UZS, QQS bilan). Bo'sh: asosiy narx amal qiladi. Yangi hisob-fakturalarga ta'sir qiladi.</label>
          <div class="flex gap-2">
            <input v-model.number="branchPrice" type="number" min="0" step="0.01" class="input" placeholder="Asosiy narx" data-testid="branch-price-input" />
            <button class="btn-secondary text-xs" :disabled="branchPrice === '' || branchPrice == null" data-testid="branch-price-save" @click="saveBranchPrice">Belgilash</button>
            <button v-if="editingBranchHas" class="text-xs text-red-500 hover:underline" @click="removeBranchPrice">Olib tashlash</button>
          </div>
        </div>
        <div><label class="text-xs text-slate-400 block mb-1">MXIK (IKPU) — 17 raqam</label><input v-model="form.mxik" class="input font-mono" maxlength="21" placeholder="09302001001000000" />
          <p v-if="mxikHint" class="text-xs text-amber-600 mt-1">{{ mxikHint }}</p></div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="text-xs text-slate-400 block mb-1">Package code</label><input v-model="form.package_code" class="input font-mono" maxlength="10" /></div>
          <div><label class="text-xs text-slate-400 block mb-1">QQS % (0 = QQSsiz)</label><input v-model="form.vat_percent" type="number" min="0" max="100" step="0.01" class="input" /></div>
        </div>
        <label class="flex items-center gap-2 text-sm"><input v-model="form.is_active" type="checkbox" /> Faol</label>
        <div class="flex items-center gap-2 pt-1">
          <input v-model="newCategory" class="input flex-1 py-1 text-sm" placeholder="Yangi kategoriya nomi" />
          <button class="btn-secondary text-xs" :disabled="newCategory.trim().length < 2" @click="addCategory">Kategoriya qo'shish</button>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button class="btn-secondary" @click="showForm = false">Bekor qilish</button>
          <button class="btn-primary" :disabled="saving || form.name.trim().length < 2 || form.price === '' || !!mxikHint" @click="save">Saqlash</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Pencil } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast()
const theme = useThemeStore()
const auth = useAuthStore()
const dark = computed(() => theme.isDark)
const fmt = v => new Intl.NumberFormat('uz-UZ').format(v)

const services = ref([]), categories = ref([]), error = ref(false)
const search = ref(''), onlyState = ref('')
const shown = computed(() => services.value.filter(s =>
  (!search.value || s.name.toLowerCase().includes(search.value.toLowerCase())) &&
  (!onlyState.value || (onlyState.value === 'sellable' ? s.sellable : s.is_active && !s.sellable))))

const costs = ref({})
const norms = reactive({ service: null, items: [], lines: [], cost: null, saving: false })
async function loadCosts() {
  if (!auth.can('warehouse:read')) return
  try { costs.value = Object.fromEntries((await api.get('/warehouse/service-costs')).data.map(c => [c.service_id, c])) } catch { costs.value = {} }
}
async function openNorms(s) {
  // Modal ma'lumot to'liq kelgach ochiladi (yuklanguncha qo'shilgan qator yo'qolib ketmasin)
  try {
    const [items, cur, cost] = await Promise.all([api.get('/warehouse/items'), api.get(`/warehouse/services/${s.id}/materials`), api.get(`/warehouse/services/${s.id}/cost`)])
    Object.assign(norms, { service: s, items: items.data, lines: cur.data.map(m => ({ item_id: m.item_id, qty: m.qty })), cost: cost.data })
  } catch (e) { toast.error(e, "Sarf normasini yuklab bo'lmadi") }
}
async function saveNorms() {
  norms.saving = true
  try {
    await api.put(`/warehouse/services/${norms.service.id}/materials`, { materials: norms.lines.filter(l => l.item_id).map(l => ({ item_id: l.item_id, qty: l.qty })) })
    norms.cost = (await api.get(`/warehouse/services/${norms.service.id}/cost`)).data
    toast.success('Sarf normasi saqlandi'); await loadCosts()
  } catch (e) { toast.error(e, "Normani saqlab bo'lmadi") } finally { norms.saving = false }
}

const showForm = ref(false), editingId = ref(null), saving = ref(false), newCategory = ref('')
const blank = () => ({ name: '', price: '', category_id: '', mxik: '', package_code: '', vat_percent: '', is_active: true })
const form = reactive(blank())
const mxikHint = computed(() => {
  const d = form.mxik.replace(/[\s-]/g, '')
  return d && !/^\d{17}$/.test(d) ? `MXIK 17 raqam bo'lishi kerak (hozir ${d.length}${/\D/.test(d) ? ', raqam bo\'lmagan belgi bor' : ''})` : ''
})

async function load() {
  error.value = false
  try {
    const [s, c] = await Promise.all([api.get('/services', { params: { include_inactive: true } }), api.get('/service-categories')])
    services.value = s.data
    categories.value = c.data
  } catch (e) { services.value = []; error.value = true; toast.error(e, "Narxnomani yuklab bo'lmadi") }
}
function openNew() { editingId.value = null; Object.assign(form, blank()); showForm.value = true }
const branchPrice = ref(''), editingBranchHas = ref(false)
function openEdit(s) {
  editingId.value = s.id
  branchPrice.value = s.branch_price ?? ''; editingBranchHas.value = s.branch_price != null
  Object.assign(form, { name: s.name, price: s.price, category_id: s.category_id || '', mxik: s.mxik || '', package_code: s.package_code || '',
                        vat_percent: s.vat_percent ?? '', is_active: s.is_active })
  showForm.value = true
}
async function save() {
  saving.value = true
  const body = { name: form.name.trim(), price: form.price, category_id: form.category_id || null, mxik: form.mxik.replace(/[\s-]/g, '') || null,
                 package_code: form.package_code.trim() || null, vat_percent: form.vat_percent === '' ? null : form.vat_percent, is_active: form.is_active }
  try {
    if (editingId.value) await api.put(`/services/${editingId.value}`, body)
    else await api.post('/services', body)
    toast.success('Xizmat saqlandi')
    showForm.value = false
    await load()
  } catch (e) { toast.error(e, "Xizmatni saqlab bo'lmadi") } finally { saving.value = false }
}
async function saveBranchPrice() {
  try { await api.put(`/services/${editingId.value}/branch-price`, { price: branchPrice.value }); toast.success('Filial narxi belgilandi'); editingBranchHas.value = true; await load() }
  catch (e) { toast.error(e, "Filial narxini belgilab bo'lmadi") }
}
async function removeBranchPrice() {
  try { await api.delete(`/services/${editingId.value}/branch-price`); toast.success('Asosiy narxga qaytdi'); branchPrice.value = ''; editingBranchHas.value = false; await load() }
  catch (e) { toast.error(e, "Filial narxini olib tashlab bo'lmadi") }
}
async function addCategory() {
  try {
    const { data } = await api.post('/service-categories', { name: newCategory.value.trim() })
    categories.value.push(data)
    form.category_id = data.id
    newCategory.value = ''
  } catch (e) { toast.error(e, "Kategoriyani qo'shib bo'lmadi") }
}
onMounted(() => { load(); loadCosts() })
</script>
