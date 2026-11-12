<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-2xl font-heading font-bold text-slate-900">Uchrashuvlar</h2>
        <p class="text-slate-500 text-sm mt-1">Bugun: {{ today }}</p>
      </div>
      <button class="btn-primary" @click="showModal = true"><Plus class="w-4 h-4" /> Uchrashuv qo'shish</button>
    </div>

    <!-- Stats -->
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div v-for="s in statusStats" :key="s.label" class="card p-4 text-center">
        <p class="text-2xl font-heading font-bold" :class="s.color">{{ s.count }}</p>
        <p class="text-xs text-slate-500 mt-1">{{ s.label }}</p>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="card p-4 flex flex-wrap gap-3">
      <input v-model="filterDate" type="date" class="input w-auto" />
      <select v-model="filterStatus" class="input w-auto">
        <option value="">Barcha status</option>
        <option value="Scheduled">Rejalashtirilgan</option>
        <option value="Completed">Yakunlangan</option>
        <option value="Cancelled">Bekor qilingan</option>
      </select>
      <button class="btn-secondary" @click="filterDate = ''; filterStatus = ''">Tozalash</button>
    </div>

    <!-- Table -->
    <div class="card">
      <div v-if="loading" class="p-12 text-center">
        <div class="animate-spin w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto mb-3"></div>
        <p class="text-slate-400 text-sm">Yuklanmoqda...</p>
      </div>

      <EmptyState v-else-if="loadError" title="Uchrashuvlarni yuklab bo'lmadi" description="Server bilan aloqa o'rnatilmadi. Qayta urinib ko'ring." action-label="Qayta urinish" @action="fetchAppointments" />

      <EmptyState v-else-if="appointments.length === 0" title="Hali uchrashuvlar yo'q" description="Birinchi uchrashuvni rejalashtiring" action-label="Uchrashuv qo'shish" @action="showModal = true" />

      <div v-else class="table-container border-0">
        <table class="table">
          <thead>
            <tr>
              <th>Bemor</th>
              <th>Shifokor</th>
              <th>Sana / Vaqt</th>
              <th>Tur</th>
              <th>Kabinet</th>
              <th>Status</th>
              <th>Amal</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in filtered" :key="a.id">
              <td class="font-medium text-slate-900">{{ a.patient_name }}</td>
              <td class="text-slate-600">{{ a.doctor }}</td>
              <td class="font-mono text-slate-600">{{ a.date }} <span class="text-cyan-600">{{ a.time }}–{{ a.end_time }}</span> <span class="text-xs text-slate-400">({{ a.duration_min }} daq)</span></td>
              <td><span class="badge badge-blue">{{ a.type }}</span><span v-if="a.override_reason" class="badge-yellow ml-1 text-[10px]" :title="'Majburan yozilgan: ' + a.override_reason">majburan</span></td>
              <td class="font-mono text-sm text-slate-500">{{ a.room || '—' }}</td>
              <td>
                <span :class="{
                  'badge-blue': a.status === 'Scheduled',
                  'badge-green': a.status === 'Completed',
                  'badge-red': a.status === 'Cancelled',
                  'badge-yellow': a.status === 'No Show',
                }">{{ statusLabel(a.status) }}</span>
              </td>
              <td>
                <div class="flex gap-1">
                  <button class="btn-ghost !px-2 !py-1.5 text-xs text-emerald-600 hover:bg-emerald-50" @click="updateStatus(a, 'Completed')">✓</button>
                  <button class="btn-ghost !px-2 !py-1.5 text-xs text-red-500 hover:bg-red-50" @click="updateStatus(a, 'Cancelled')">✕</button>
                </div>
              </td>
            </tr>
            <tr v-if="filtered.length === 0">
              <td colspan="7" class="py-12 text-center text-slate-400">Uchrashuvlar topilmadi</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <WaitlistPanel :doctors="doctorList" :types="appointmentTypes" @booked="fetchAppointments" />

    <!-- Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3 class="font-heading font-semibold text-slate-900">Yangi uchrashuv</h3>
          <button @click="showModal = false" class="btn-ghost !px-2 !py-2"><X class="w-4 h-4" /></button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="addAppointment" class="space-y-4">
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="text-sm font-medium text-slate-700 block mb-1.5">Bemor ismi *</label>
                <input v-model="form.patient_name" class="input" placeholder="Aziza Karimova" required />
              </div>
              <div>
                <label class="text-sm font-medium text-slate-700 block mb-1.5">Shifokor *</label>
                <select v-model="form.doctor" class="input" required>
                  <option value="" disabled>— Tanlang —</option>
                  <option v-for="d in doctorList" :key="d" :value="d">{{ d }}</option>
                </select>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="text-sm font-medium text-slate-700 block mb-1.5">Sana *</label>
                <input v-model="form.date" type="date" class="input" required />
              </div>
              <div>
                <label class="text-sm font-medium text-slate-700 block mb-1.5">Vaqt *</label>
                <input v-model="form.time" type="time" class="input" required />
              </div>
            </div>
            <div v-if="form.doctor && form.date" class="-mt-1">
              <p class="text-xs text-slate-400 mb-1.5">Bo'sh vaqtlar (ish jadvali, band qabullar hisobga olingan)</p>
              <p v-if="slotsLoading" class="text-xs text-slate-400">Yuklanmoqda...</p>
              <p v-else-if="slotsError" class="text-xs text-red-500">Yuklab bo'lmadi. <button type="button" class="underline" @click="loadSlots">Qayta urinish</button></p>
              <p v-else-if="!slots.length" class="text-xs text-amber-600">Bu kuni bo'sh vaqt yo'q (shifokor ishlamaydi yoki band)</p>
              <div v-else class="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                <button v-for="sl in slots" :key="sl.time" type="button" @click="form.time = sl.time"
                  :class="['px-2 py-1 rounded-lg text-xs font-mono border', form.time === sl.time ? 'bg-cyan-600 text-white border-cyan-600' : 'border-slate-200 text-slate-600 hover:border-cyan-500']">{{ sl.time }}</button>
              </div>
            </div>
            <div>
              <label class="text-sm font-medium text-slate-700 block mb-1.5">Tur</label>
              <select v-model="form.type" class="input">
                <option v-for="t in appointmentTypes" :key="t.id" :value="t.name">{{ t.name }} ({{ t.duration_min }} daq)</option>
              </select>
            </div>
            <div>
              <label class="text-sm font-medium text-slate-700 block mb-1.5">Kabinet</label>
              <select v-model="form.room_id" class="input">
                <option value="">Shifokorning standart kabineti</option>
                <option v-for="r in roomList" :key="r.id" :value="r.id">{{ r.name }}{{ r.description ? ' — ' + r.description : '' }}</option>
              </select>
            </div>
            <div v-if="auth.can('appointments:override')">
              <label class="text-sm font-medium text-slate-700 block mb-1.5">Majburan yozish sababi <span class="text-xs text-slate-400 font-normal">(faqat ish vaqtidan tashqari bo'lsa; band vaqtga yozib bo'lmaydi)</span></label>
              <input v-model="form.override_reason" class="input" maxlength="500" placeholder="Masalan: shoshilinch holat, shifokor bilan kelishilgan" />
            </div>
            <div class="flex gap-3 pt-2">
              <button type="button" class="btn-secondary flex-1" @click="showModal = false">Bekor</button>
              <button type="submit" class="btn-primary flex-1">Saqlash</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { Plus, X } from 'lucide-vue-next'
import EmptyState from '@/components/ui/EmptyState.vue'
import WaitlistPanel from '@/components/WaitlistPanel.vue'
import { useAuthStore } from '@/stores/auth'
import api, { fetchAll } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

const appointments = ref([])
const loading = ref(true)
const loadError = ref(false)
const auth = useAuthStore()
const doctorList = ref([])
const doctorIds = {}
const filterDate = ref('')
const filterStatus = ref('')
const showModal = ref(false)
const today = new Date().toLocaleDateString('uz-UZ')

const form = reactive({ patient_name: '', doctor: '', date: '', time: '10:00', type: 'Konsultatsiya', room_id: '', override_reason: '', notes: '' })

const filtered = computed(() => {
  let list = appointments.value
  if (filterDate.value) list = list.filter(a => a.date === filterDate.value)
  if (filterStatus.value) list = list.filter(a => a.status === filterStatus.value)
  return list
})

const statusStats = computed(() => [
  { label: 'Rejalashtirilgan', count: appointments.value.filter(a => a.status === 'Scheduled').length, color: 'text-blue-500' },
  { label: 'Yakunlangan', count: appointments.value.filter(a => a.status === 'Completed').length, color: 'text-emerald-500' },
  { label: 'Bekor qilingan', count: appointments.value.filter(a => a.status === 'Cancelled').length, color: 'text-red-500' },
  { label: 'Jami', count: appointments.value.length, color: 'text-slate-700' },
])

function statusLabel(s) {
  const map = { Scheduled: 'Rejalashtirilgan', Completed: 'Yakunlangan', Cancelled: 'Bekor', 'No Show': 'Kelmadi' }
  return map[s] || s
}

async function fetchAppointments() {
  loading.value = true
  loadError.value = false
  try {
    const { data } = await api.get('/appointments')
    appointments.value = data
  } catch (e) {
    appointments.value = []
    loadError.value = true
    toast.error(e, "Uchrashuvlarni yuklab bo'lmadi")
  } finally { loading.value = false }
}

const slots = ref([]), slotsLoading = ref(false), slotsError = ref(false)
async function loadSlots() {
  const id = doctorIds[form.doctor]
  if (!id || !form.date) { slots.value = []; return }
  slotsLoading.value = true
  slotsError.value = false
  try {
    const params = { date: form.date, type: form.type }
    if (form.room_id) params.room_id = form.room_id
    slots.value = (await api.get(`/staff/${id}/slots`, { params })).data.slots
  } catch (e) {
    slots.value = []
    slotsError.value = true
    toast.error(e, "Bo'sh vaqtlarni yuklab bo'lmadi")
  } finally { slotsLoading.value = false }
}
watch(() => [form.doctor, form.date, form.type, form.room_id], loadSlots)

const roomList = ref([])
async function fetchRooms() {
  try { roomList.value = (await api.get('/rooms')).data } catch (e) { roomList.value = []; toast.error(e, "Kabinetlarni yuklab bo'lmadi") }
}

const appointmentTypes = ref([])
async function fetchTypes() {
  try {
    const { data } = await api.get('/appointment-types')
    appointmentTypes.value = data
    if (data.length && !data.some(t => t.name === form.type)) form.type = data[0].name
  } catch (e) {
    appointmentTypes.value = []
    toast.error(e, "Qabul turlarini yuklab bo'lmadi")
  }
}

async function fetchDoctors() {
  try {
    const { data } = await api.get('/staff', { params: { role: 'Doctor' } })
    doctorList.value = data.map(s => s.name)
    data.forEach(s => { doctorIds[s.name] = s.id })
  } catch (e) {
    doctorList.value = []
    toast.error(e, "Shifokorlar ro'yxatini yuklab bo'lmadi")
  }
}

const toast = useToast()

async function addAppointment() {
  try {
    // Bemor nomi bo'yicha haqiqiy patient_id topiladi 
    const patients = await fetchAll('/patients', { search: form.patient_name })
    const patient = patients.find(p => p.name.toLowerCase() === form.patient_name.trim().toLowerCase())
    if (!patient) {
      toast.error(`"${form.patient_name}" nomli bemor topilmadi`)
      return
    }
    const { data } = await api.post('/appointments', { ...form, room_id: form.room_id || null, override_reason: form.override_reason || null, patient_id: patient.id, patient_name: patient.name })
    appointments.value.push(data)
    toast.success('Uchrashuv rejalashtirildi')
    showModal.value = false
  } catch (e) {
    toast.error(e, "Uchrashuvni saqlab bo'lmadi")
  }
}

async function updateStatus(appt, status) {
  const previous = appt.status
  appt.status = status
  try {
    await api.patch(`/appointments/${appt.id}/status`, null, { params: { status } })
  } catch (e) {
    appt.status = previous // xato bo'lsa rollback
    toast.error(e, "Statusni o'zgartirib bo'lmadi")
  }
}

onMounted(() => { fetchAppointments(); fetchDoctors(); fetchTypes(); fetchRooms() })
</script>
