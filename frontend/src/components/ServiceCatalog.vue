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
        <thead><tr><th>Xizmat</th><th>Kategoriya</th><th class="text-right">Narx (UZS)</th><th>MXIK</th><th>Qadoq</th><th>QQS</th><th>Holat</th><th></th></tr></thead>
        <tbody>
          <tr v-for="s in shown" :key="s.id" :class="s.is_active ? '' : 'opacity-60'">
            <td class="font-medium">{{ s.name }}</td>
            <td class="text-sm text-slate-500">{{ s.category || '—' }}</td>
            <td class="text-right font-mono">{{ fmt(s.price) }}</td>
            <td class="font-mono text-xs">{{ s.mxik || '—' }}</td>
            <td class="font-mono text-xs">{{ s.package_code || '—' }}</td>
            <td class="text-sm">{{ s.vat_percent != null ? s.vat_percent + '%' : '—' }}</td>
            <td>
              <span v-if="!s.is_active" class="badge-slate">Nofaol</span>
              <span v-else-if="s.sellable" class="badge-green">Sotiladi</span>
              <span v-else class="badge-yellow" :title="'Yetishmaydi: ' + s.missing.join(', ')">Kod to'liq emas</span>
            </td>
            <td><button v-if="auth.can('services:write')" class="text-slate-400 hover:text-cyan-600" title="Tahrirlash" @click="openEdit(s)"><Pencil class="w-4 h-4" /></button></td>
          </tr>
        </tbody>
      </table>
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
function openEdit(s) {
  editingId.value = s.id
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
async function addCategory() {
  try {
    const { data } = await api.post('/service-categories', { name: newCategory.value.trim() })
    categories.value.push(data)
    form.category_id = data.id
    newCategory.value = ''
  } catch (e) { toast.error(e, "Kategoriyani qo'shib bo'lmadi") }
}
onMounted(load)
</script>
