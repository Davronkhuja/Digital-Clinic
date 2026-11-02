<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ lang.t('patients.title') }}</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">{{ total }} {{ lang.t('patients.subtitle') }}</p>
      </div>
      <button class="btn-primary" @click="openAdd"><Plus class="w-4 h-4" /> {{ lang.t('patients.add') }}</button>
    </div>

    <div class="card">
      <div :class="['p-4 border-b flex flex-col sm:flex-row gap-3', dark ? 'border-slate-800' : 'border-slate-100']">
        <div class="relative flex-1">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input v-model="search" class="input pl-9" :placeholder="lang.t('patients.search')" />
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
              <th>To'lov (UZS)</th>
              <th>{{ lang.t('patients.status') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in filtered" :key="p.id">
              <td>
                <span :class="['font-mono text-xs px-2 py-1 rounded-lg font-semibold', dark ? 'bg-slate-800 text-cyan-400' : 'bg-cyan-50 text-cyan-700']">
                  {{ p.patient_id }}
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
              <td>
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
              <td colspan="9" :class="['py-12 text-center text-sm', dark ? 'text-slate-500' : 'text-slate-400']">Bemor topilmadi</td>
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
              <div class="col-span-2">
                <label :class="lbl">Manzil</label>
                <input v-model="form.address" class="input" placeholder="Toshkent, Yunusobod tumani" />
              </div>
              <div class="col-span-2">
                <label :class="lbl">Allergiyalar</label>
                <input v-model="form.allergies" class="input" placeholder="Penitsillin, Aspirin..." />
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
import { ref, computed, onMounted, reactive } from 'vue'
import { RouterLink } from 'vue-router'
import { Plus, Search, Download, X, Check, Pencil, Trash2 } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useLanguageStore } from '@/stores/language'
import { useThemeStore } from '@/stores/theme'
import { usePhoneMask } from '@/composables/usePhoneMask'

const lang  = useLanguageStore()
const theme = useThemeStore()
const dark  = computed(() => theme.isDark)
const lbl   = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])
const { maskPhone, onPhoneKeydown } = usePhoneMask()

const patients    = ref([])
const loading     = ref(true)
const search      = ref('')
const filterStatus = ref('')
const showModal   = ref(false)
const saving      = ref(false)
const editingId   = ref(null)

// Doctor list from staff
const doctorList = ref([])

const bloodTypes = ['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']

const defaultForm = () => ({
  name: '', phone: '', age: '', birth_date: '', gender: 'female',
  blood_type: null, doctor: '', address: '', allergies: ''
})
const form = reactive(defaultForm())

// Payments map: patient name → total paid
const patientPayments = ref({})

const total    = computed(() => patients.value.length)
const filtered = computed(() => {
  let list = patients.value
  if (search.value)      list = list.filter(p => p.name.toLowerCase().includes(search.value.toLowerCase()) || p.patient_id?.includes(search.value))
  if (filterStatus.value) list = list.filter(p => p.status === filterStatus.value)
  return list
})

const gradients = ['bg-gradient-to-br from-cyan-500 to-blue-600', 'bg-gradient-to-br from-violet-500 to-purple-600', 'bg-gradient-to-br from-emerald-500 to-teal-600', 'bg-gradient-to-br from-orange-500 to-red-600', 'bg-gradient-to-br from-pink-500 to-rose-500']
function avatarBg(name) { return gradients[(name?.charCodeAt(0) || 0) % gradients.length] }

function generateId(index) {
  const d = new Date()
  const date = `${d.getFullYear()}${String(d.getMonth()+1).padStart(2,'0')}${String(d.getDate()).padStart(2,'0')}`
  const seq  = String(index + 1).padStart(3, '0')
  return `B-${date}-${seq}`
}

function fmtMoney(v) {
  return new Intl.NumberFormat('uz-UZ').format(v)
}

async function fetchPatients() {
  loading.value = true
  try {
    const { data } = await api.get('/patients', { params: { limit: 100 } })
    patients.value = data.map((p, i) => ({ ...p, patient_id: p.patient_id || generateId(i) }))
  } catch {
    patients.value = [
      { id: '1', patient_id: 'B-20260224-001', name: 'Aziza Karimova',  phone: '+998 90 123-45-67', age: 34, gender: 'female', last_visit: '2026-02-20', status: 'Active',   doctor: 'Dr. Rustamov',  blood_type: 'A+' },
      { id: '2', patient_id: 'B-20260224-002', name: 'Bobur Aliyev',    phone: '+998 91 234-56-78', age: 45, gender: 'male',   last_visit: '2026-02-18', status: 'Active',   doctor: 'Dr. Karimov',   blood_type: 'O+' },
      { id: '3', patient_id: 'B-20260224-003', name: 'Dilnoza Rahimova',phone: '+998 93 345-67-89', age: 28, gender: 'female', last_visit: '2026-02-15', status: 'Inactive', doctor: 'Dr. Yusupov',  blood_type: null },
      { id: '4', patient_id: 'B-20260224-004', name: 'Eldor Toshmatov', phone: '+998 94 456-78-90', age: 52, gender: 'male',   last_visit: '2026-02-22', status: 'Active',   doctor: 'Dr. Rustamov',  blood_type: 'B+' },
      { id: '5', patient_id: 'B-20260224-005', name: 'Feruza Umarova',  phone: '+998 95 567-89-01', age: 39, gender: 'female', last_visit: '2026-02-21', status: 'Active',   doctor: 'Dr. Karimov',   blood_type: 'AB-' },
    ]
  } finally { loading.value = false }
}

async function fetchDoctors() {
  try {
    const { data } = await api.get('/staff')
    doctorList.value = data.filter(s => s.role === 'Doctor').map(s => s.name)
  } catch {
    doctorList.value = ['Dr. Rustamov', 'Dr. Karimov', 'Dr. Yusupov']
  }
}

async function fetchPayments() {
  try {
    const { data } = await api.get('/finance/transactions')
    const map = {}
    data.filter(t => t.type === 'income' && t.patient_name).forEach(t => {
      map[t.patient_name] = (map[t.patient_name] || 0) + t.amount
    })
    patientPayments.value = map
  } catch {
    // demo: Aziza Karimova paid
    patientPayments.value = { 'Aziza Karimova': 700000, 'Bobur Aliyev': 450000, 'Eldor Toshmatov': 250000 }
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
    gender: p.gender, blood_type: p.blood_type, doctor: p.doctor || '', address: p.address || '', allergies: p.allergies || ''
  })
  showModal.value = true
}
function closeModal() { showModal.value = false; editingId.value = null }

async function savePatient() {
  if (!form.name) return
  saving.value = true
  await new Promise(r => setTimeout(r, 400))
  if (editingId.value) {
    const i = patients.value.findIndex(p => p.id === editingId.value)
    if (i >= 0) patients.value[i] = { ...patients.value[i], ...form }
    api.put(`/patients/${editingId.value}`, form).catch(() => {})
  } else {
    const newP = {
      ...form,
      id: Date.now().toString(),
      patient_id: generateId(patients.value.length),
      status: 'Active',
      last_visit: new Date().toISOString().slice(0, 10)
    }
    patients.value.push(newP)
    api.post('/patients', form).catch(() => {})
  }
  saving.value = false; closeModal()
}

async function deletePatient(id) {
  if (!confirm('Bemorni o\'chirishni tasdiqlaysizmi?')) return
  patients.value = patients.value.filter(p => p.id !== id)
  api.delete(`/patients/${id}`).catch(() => {})
}

function exportCSV() {
  const header = ['ID', 'Ism', 'Telefon', 'Yosh', 'Jins', 'Qon guruhi', 'Shifokor', 'Status']
  const rows = filtered.value.map(p => [p.patient_id, p.name, p.phone, p.age, p.gender, p.blood_type || '', p.doctor, p.status])
  const csv = [header, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' }))
  a.download = `patients_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
}

onMounted(() => { fetchPatients(); fetchDoctors(); fetchPayments() })
</script>

<style scoped>
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>