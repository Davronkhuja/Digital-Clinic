<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('patients.title') }}</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">{{ total }} {{ lang.t('patients.subtitle') }}</p>
      </div>
      <button class="btn-primary" @click="openAdd"><Plus class="w-4 h-4" /> {{ lang.t('patients.add') }}</button>
    </div>

    <div v-if="canMerge" class="flex gap-1">
      <button v-for="t in tabs" :key="t.key" :class="['px-4 py-2 text-sm font-medium rounded-lg transition-colors', tab === t.key ? 'bg-cyan-600 text-white' : (dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-600 hover:bg-slate-100')]" @click="tab = t.key">{{ t.label }}</button>
    </div>

    <div v-if="tab === 'duplicates' && canMerge" class="card">
      <PatientDuplicates @merged="fetchPatients" />
    </div>

    <div v-else class="card">
      <div :class="['p-4 border-b flex flex-col sm:flex-row gap-3', dark ? 'border-slate-800' : 'border-slate-100']">
        <div class="relative flex-1">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input v-model="search" class="input pl-9" :placeholder="lang.t('patients.search')" :title="searchHint" />
          <p :class="['text-xs mt-1.5', dark ? 'text-slate-500' : 'text-slate-400']">{{ searchHint }}</p>
        </div>
        <div class="flex gap-2">
          <select v-model="filterStatus" class="input w-auto">
            <option value="">{{ lang.t('patients.all_status') }}</option>
            <option value="Active">{{ lang.t('patients.active') }}</option>
            <option value="Inactive">{{ lang.t('patients.inactive') }}</option>
          </select>
          <button class="btn-secondary" @click="exportCSV"><Download class="w-4 h-4" /> Export</button>
        </div>
      </div>

      <div v-if="loading" class="p-12 text-center">
        <div class="animate-spin w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto mb-3"></div>
        <p class="text-slate-400 text-sm">Yuklanmoqda...</p>
      </div>

      <div v-else-if="loadError" class="p-4">
        <EmptyState title="Bemorlarni yuklab bo'lmadi" description="Server bilan aloqa o'rnatilmadi. Qayta urinib ko'ring." action-label="Qayta urinish" @action="fetchPatients" />
      </div>

      <EmptyState v-else-if="patients.length === 0" title="Hali bemorlar yo'q" description="Birinchi bemorni qo'shing" action-label="Bemor qo'shish" @action="openAdd" />

      <div v-else class="table-container rounded-none border-0">
        <table class="table">
          <thead>
            <tr>
              <th>ID</th>
              <th>{{ lang.t('patients.fullname') }}</th>
              <th>{{ lang.t('patients.phone') }}</th>
              <th>Yosh / Jins</th>
              <th>Qon guruhi</th>
              <th>{{ lang.t('patients.doctor') }}</th>
              <th v-if="showPayments">To'lov (UZS)</th>
              <th>{{ lang.t('patients.status') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in filtered" :key="p.id">
              <td>
                <span :class="['font-mono text-xs px-2 py-1 rounded-lg font-semibold', dark ? 'bg-slate-800 text-cyan-400' : 'bg-cyan-50 text-cyan-700']">
                  {{ p.id.slice(0, 8) }}
                </span>
              </td>
              <td>
                <div class="flex items-center gap-2.5">
                  <div :class="['w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0', avatarBg(p.name)]">
                    {{ p.name[0] }}
                  </div>
                  <RouterLink :to="`/patients/${p.id}`" :class="['font-medium hover:text-cyan-600 transition-colors', dark ? 'text-slate-200' : 'text-slate-900']">
                    {{ p.name }}
                  </RouterLink>
                </div>
              </td>
              <td :class="['font-mono text-sm', dark ? 'text-slate-400' : 'text-slate-600']">{{ p.phone }}</td>
              <td :class="dark ? 'text-slate-400' : 'text-slate-600'">{{ p.age }} / {{ p.gender === 'male' ? 'Erkak' : 'Ayol' }}</td>
              <td>
                <span v-if="p.blood_type" :class="['badge font-semibold', dark ? 'bg-red-900/40 text-red-400' : 'bg-red-50 text-red-600']">{{ p.blood_type }}</span>
                <span v-else :class="['text-xs', dark ? 'text-slate-600' : 'text-slate-300']">—</span>
              </td>
              <td :class="['text-sm', dark ? 'text-slate-400' : 'text-slate-600']">{{ p.doctor || '—' }}</td>
              <td v-if="showPayments">
                <span v-if="patientPayments[p.name]" class="font-mono text-sm font-semibold text-emerald-500">
                  {{ fmtMoney(patientPayments[p.name]) }}
                </span>
                <span v-else :class="['text-xs', dark ? 'text-slate-600' : 'text-slate-300']">—</span>
              </td>
              <td>
                <span :class="p.status === 'Active' ? 'badge-green' : 'badge-slate'">
                  {{ p.status === 'Active' ? 'Faol' : 'Nofaol' }}
                </span>
              </td>
              <td>
                <div class="flex items-center gap-1">
                  <RouterLink :to="`/patients/${p.id}`" :class="['flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium transition-colors', dark ? 'text-cyan-400 hover:bg-cyan-500/10' : 'text-cyan-600 hover:bg-cyan-50']">Ko'rish</RouterLink>
                  <button @click="openEdit(p)" :class="['flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium transition-colors', dark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-100']"><Pencil class="w-3.5 h-3.5" /></button>
                  <button @click="deletePatient(p.id)" class="px-2 py-1.5 rounded-lg text-xs font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"><Trash2 class="w-3.5 h-3.5" /></button>
                </div>
              </td>
            </tr>
            <tr v-if="filtered.length === 0">
              <td :colspan="showPayments ? 9 : 8" :class="['py-12 text-center text-sm', dark ? 'text-slate-500' : 'text-slate-400']">Bemor topilmadi</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Add/Edit Modal -->
    <Transition name="modal-fade">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div :class="['w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-fade-in max-h-[92vh] flex flex-col', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
          <div :class="['flex items-center justify-between px-6 py-4 border-b flex-shrink-0', dark ? 'border-slate-800' : 'border-slate-200']">
            <div>
              <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ editingId ? 'Bemorni tahrirlash' : "Yangi bemor qo'shish" }}</h3>
              <p v-if="!editingId" class="text-xs text-slate-400 mt-0.5">ID avtomatik beriladi</p>
            </div>
            <button @click="closeModal" :class="['p-1.5 rounded-lg', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><X class="w-4 h-4" /></button>
          </div>

          <div class="overflow-y-auto flex-1 p-6 space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div class="col-span-2">
                <label :class="lbl">To'liq ism *</label>
                <input v-model="form.name" class="input" placeholder="Aziza Karimova" />
              </div>
              <div>
                <label :class="lbl">Telefon *</label>
                <input v-model="form.phone" class="input font-mono" placeholder="+998 90 123-45-67"
                  @input="e => { form.phone = maskPhone(e.target.value); e.target.value = form.phone }"
                  @keydown="onPhoneKeydown" maxlength="17" />
              </div>
              <div>
                <label :class="lbl">Tug'ilgan sana</label>
                <input v-model="form.birth_date" type="date" class="input" />
              </div>
              <div>
                <label :class="lbl">Yosh</label>
                <input v-model.number="form.age" type="number" class="input" placeholder="25" min="0" max="150" />
              </div>
              <div>
                <label :class="lbl">Jins *</label>
                <select v-model="form.gender" class="input">
                  <option value="female">Ayol</option>
                  <option value="male">Erkak</option>
                </select>
              </div>
              <div>
                <label :class="lbl">Qon guruhi</label>
                <select v-model="form.blood_type" class="input">
                  <option :value="null">— Tanlanmagan —</option>
                  <option v-for="bg in bloodTypes" :key="bg" :value="bg">{{ bg }}</option>
                </select>
              </div>
              <div>
                <label :class="lbl">Biriktilgan shifokor</label>
                <select v-model="form.doctor" class="input">
                  <option value="">— Tanlanmagan —</option>
                  <option v-for="d in doctorList" :key="d" :value="d">{{ d }}</option>
                </select>
              </div>
              <div>
                <label :class="lbl">PINFL</label>
                <input v-model="form.pinfl" class="input font-mono" placeholder="14 ta raqam" maxlength="14" inputmode="numeric"
                  @input="form.pinfl = form.pinfl.replace(/\D/g, '')" />
              </div>
              <div class="col-span-2">
                <label :class="lbl">Manzil</label>
                <input v-model="form.address" class="input" placeholder="Toshkent, Yunusobod tumani" />
              </div>
              <div class="col-span-2">
                <label :class="lbl">Allergiyalar</label>
                <input v-model="form.allergies" class="input" placeholder="Penitsillin, Aspirin..." />
              </div>
              <div class="col-span-2">
                <label :class="lbl">Bemor manbasi</label>
                <select v-model="form.source" class="input">
                  <option value="">Ko'rsatilmagan</option><option value="reklama">Reklama</option><option value="tavsiya">Tavsiya</option>
                  <option value="instagram">Instagram</option><option value="onlayn">Onlayn</option><option value="boshqa">Boshqa</option>
                </select>
              </div>
            </div>
          </div>

          <div :class="['px-6 py-4 border-t flex gap-3 flex-shrink-0', dark ? 'border-slate-800 bg-slate-900/50' : 'border-slate-100 bg-slate-50']">
            <button class="btn-secondary flex-1" @click="closeModal">Bekor</button>
            <button class="btn-primary flex-1" @click="savePatient" :disabled="saving">
              <Check class="w-4 h-4" />{{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Plus, Search, Download, X, Check, Pencil, Trash2 } from 'lucide-vue-next'
import api, { fetchAll } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useLanguageStore } from '@/stores/language'
import { useThemeStore } from '@/stores/theme'
import { usePhoneMask } from '@/composables/usePhoneMask'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/ui/EmptyState.vue'
import PatientDuplicates from '@/components/PatientDuplicates.vue'

const lang  = useLanguageStore()
const theme = useThemeStore()
const dark  = computed(() => theme.isDark)
const lbl   = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])
const { maskPhone, onPhoneKeydown } = usePhoneMask()

const auth        = useAuthStore()
const canMerge    = computed(() => auth.can('patients:merge'))
const tab         = ref('list')
const tabs        = [{ key: 'list', label: 'Ro\'yxat' }, { key: 'duplicates', label: 'Dublikatlar' }]
const searchHint  = "Ism, telefon (90 123 45 67), PINFL (14 raqam) yoki tug'ilgan sana (17.05.1990 yoki 1990-05-17)"
const patients    = ref([])
const loading     = ref(true)
const loadError   = ref(false)
const search      = ref('')
const filterStatus = ref('')
const showModal   = ref(false)
const saving      = ref(false)
const editingId   = ref(null)

// Doctor list from staff
const doctorList = ref([])

const bloodTypes = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']

const toast = useToast()

const defaultForm = () => ({
  name: '', phone: '', age: '', birth_date: '', gender: 'female',
  blood_type: null, doctor: '', address: '', allergies: '', pinfl: '', source: ''
})
const form = reactive(defaultForm())

// Payments map: patient name → total paid
const patientPayments = ref({})
const showPayments = ref(false)

const total    = computed(() => patients.value.length)
const filtered = computed(() => {
  let list = patients.value // qidiruv serverda (ism, telefon raqamlari, PINFL, sana)
  if (filterStatus.value) list = list.filter(p => p.status === filterStatus.value)
  return list
})

const gradients = ['bg-gradient-to-br from-cyan-500 to-blue-600', 'bg-gradient-to-br from-violet-500 to-purple-600', 'bg-gradient-to-br from-emerald-500 to-teal-600', 'bg-gradient-to-br from-orange-500 to-red-600', 'bg-gradient-to-br from-pink-500 to-rose-500']
function avatarBg(name) { return gradients[(name?.charCodeAt(0) || 0) % gradients.length] }

function fmtMoney(v) {
  return new Intl.NumberFormat('uz-UZ').format(v)
}

async function fetchPatients() {
  loading.value = true
  loadError.value = false
  try {
    patients.value = await fetchAll('/patients', search.value.trim() ? { search: search.value.trim() } : {})
  } catch (e) {
    patients.value = []
    loadError.value = true
    toast.error(e, "Bemorlarni yuklab bo'lmadi")
  } finally { loading.value = false }
}

async function fetchDoctors() {
  try {
    const { data } = await api.get('/staff', { params: { role: 'Doctor' } })
    doctorList.value = data.map(s => s.name)
  } catch (e) {
    doctorList.value = []
    toast.error(e, "Shifokorlar ro'yxatini yuklab bo'lmadi")
  }
}

async function fetchPayments() {
  try {
    const { data } = await api.get('/finance/transactions', { params: { type: 'income' } })
    const map = {}
    data.filter(t => t.type === 'income' && t.patient_name).forEach(t => {
      map[t.patient_name] = (map[t.patient_name] || 0) + t.amount
    })
    patientPayments.value = map
    showPayments.value = true
  } catch (e) {
    // 403 — moliya ruxsati yo'q (kutilgan holat), to'lov ustuni yashiriladi
    patientPayments.value = {}
    showPayments.value = false
    if (e?.response?.status !== 403) toast.error(e, "To'lovlarni yuklab bo'lmadi")
  }
}

function openAdd() {
  editingId.value = null
  Object.assign(form, defaultForm())
  showModal.value = true
}
function openEdit(p) {
  editingId.value = p.id
  Object.assign(form, {
    name: p.name, phone: p.phone, age: p.age, birth_date: p.birth_date || '',
    gender: p.gender, blood_type: p.blood_type, doctor: p.doctor || '', address: p.address || '', allergies: p.allergies || '', pinfl: p.pinfl || '', source: p.source || ''
  })
  showModal.value = true
}
function closeModal() { showModal.value = false; editingId.value = null }

async function savePatient() {
  if (!form.name) return
  saving.value = true
  // Backend age: int, bo'sh satrlar -> null
  const payload = { ...form, age: Number(form.age), blood_type: form.blood_type || null,
                    doctor: form.doctor || null, address: form.address || null, allergies: form.allergies || null, pinfl: form.pinfl || null, source: form.source || null }
  try {
    if (editingId.value) {
      const { data } = await api.put(`/patients/${editingId.value}`, payload)
      const i = patients.value.findIndex(p => p.id === editingId.value)
      if (i >= 0) patients.value[i] = { ...patients.value[i], ...data }
      toast.success("Bemor ma'lumotlari yangilandi")
    } else {
      const { data } = await api.post('/patients', payload)
      patients.value.push(data)
      toast.success("Bemor qo'shildi")
    }
    closeModal()
  } catch (e) {
    toast.error(e, "Bemorni saqlab bo'lmadi")
  } finally {
    saving.value = false
  }
}

async function deletePatient(id) {
  if (!confirm('Bemorni o\'chirishni tasdiqlaysizmi?')) return
  try {
    await api.delete(`/patients/${id}`)
    patients.value = patients.value.filter(p => p.id !== id)
    toast.success("Bemor o'chirildi")
  } catch (e) {
    toast.error(e, "Bemorni o'chirib bo'lmadi")
  }
}

function exportCSV() {
  const header = ['ID', 'Ism', 'Telefon', 'Yosh', 'Jins', 'Qon guruhi', 'Shifokor', 'Status']
  const rows = filtered.value.map(p => [p.id, p.name, p.phone, p.age, p.gender, p.blood_type || '', p.doctor || '', p.status])
  const csv = [header, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' }))
  a.download = `patients_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

let searchTimer
watch(search, () => { clearTimeout(searchTimer); searchTimer = setTimeout(fetchPatients, 300) })

onMounted(() => { fetchPatients(); fetchDoctors(); fetchPayments() })
</script>

<style scoped>
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>