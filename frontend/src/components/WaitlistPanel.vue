<template>
  <div class="card">
    <button class="w-full flex items-center justify-between px-5 py-4 text-left" @click="open = !open">
      <span :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Kutish ro'yxati <span class="text-sm font-normal text-slate-400">({{ entries.length }})</span></span>
      <ChevronDown :class="['w-4 h-4 text-slate-400 transition-transform', open ? 'rotate-180' : '']" />
    </button>

    <div v-if="open" :class="['border-t p-5 space-y-5', dark ? 'border-slate-800' : 'border-slate-100']">
      <form class="grid grid-cols-2 sm:grid-cols-6 gap-2 items-end" @submit.prevent="add">
        <div class="col-span-2"><label class="text-xs text-slate-400 block mb-1">Bemor *</label><input v-model="form.patient_name" class="input" placeholder="Aziza Karimova" required /></div>
        <div><label class="text-xs text-slate-400 block mb-1">Shifokor *</label>
          <select v-model="form.doctor" class="input" required><option value="" disabled>—</option><option v-for="d in doctors" :key="d" :value="d">{{ d }}</option></select></div>
        <div><label class="text-xs text-slate-400 block mb-1">Tur</label>
          <select v-model="form.type" class="input"><option v-for="t in types" :key="t.id" :value="t.name">{{ t.name }}</option></select></div>
        <div><label class="text-xs text-slate-400 block mb-1">Sanadan</label><input v-model="form.date_from" type="date" class="input" /></div>
        <div><label class="text-xs text-slate-400 block mb-1">Sanagacha</label><input v-model="form.date_to" type="date" class="input" :min="form.date_from" /></div>
        <div class="col-span-2 sm:col-span-5"><input v-model="form.notes" class="input" placeholder="Izoh (masalan: faqat ertalab)" /></div>
        <button class="btn-primary text-sm" :disabled="saving"><Plus class="w-4 h-4" /> Qo'shish</button>
      </form>

      <p v-if="loading" class="text-sm text-slate-400">Yuklanmoqda...</p>
      <EmptyState v-else-if="error" title="Kutish ro'yxatini yuklab bo'lmadi" action-label="Qayta urinish" @action="load" />
      <EmptyState v-else-if="!entries.length" title="Kutuvchi yo'q" description="Bo'sh vaqt topilmaganda bemorni shu yerga qo'shing" />
      <ul v-else class="divide-y" :class="dark ? 'divide-slate-800' : 'divide-slate-100'">
        <li v-for="e in entries" :key="e.id" class="py-3 space-y-2">
          <div class="flex items-center gap-3 flex-wrap text-sm">
            <span :class="['font-medium', dark ? 'text-slate-200' : 'text-slate-900']">{{ e.patient_name }}</span>
            <span class="font-mono text-xs text-slate-400">{{ e.patient_phone }}</span>
            <span class="text-slate-500">{{ e.doctor }}</span>
            <span class="badge-blue">{{ e.type }}</span>
            <span class="text-xs text-slate-400">{{ e.date_from }} – {{ e.date_to || 'cheklovsiz' }}</span>
            <span v-if="e.notes" class="text-xs text-slate-400 truncate flex-1">{{ e.notes }}</span>
            <span class="flex-1"></span>
            <button class="text-xs text-cyan-600 hover:underline" @click="toggleSuggest(e)">{{ picking === e.id ? 'Yopish' : 'Vaqt tanlash' }}</button>
            <button class="text-xs text-red-500 hover:underline" @click="cancel(e)">Bekor qilish</button>
          </div>
          <div v-if="picking === e.id" class="pl-1">
            <p v-if="sugLoading" class="text-xs text-slate-400">Yuklanmoqda...</p>
            <p v-else-if="!suggestions.length" class="text-xs text-amber-600">Yaqin kunlarda bo'sh vaqt yo'q</p>
            <div v-else class="flex flex-wrap gap-1.5">
              <button v-for="s in suggestions" :key="s.date + s.time" class="px-2 py-1 rounded-lg text-xs font-mono border border-slate-200 hover:border-cyan-500 hover:text-cyan-600" @click="book(e, s)">{{ s.date }} {{ s.time }}</button>
            </div>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ChevronDown, Plus } from 'lucide-vue-next'
import api, { fetchAll } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import EmptyState from '@/components/ui/EmptyState.vue'

defineProps({ doctors: { type: Array, default: () => [] }, types: { type: Array, default: () => [] } })
const emit = defineEmits(['booked'])
const toast = useToast()
const theme = useThemeStore()
const dark = computed(() => theme.isDark)

const open = ref(false)
const entries = ref([]), loading = ref(true), error = ref(false), saving = ref(false)
const picking = ref(null), suggestions = ref([]), sugLoading = ref(false)
const form = reactive({ patient_name: '', doctor: '', type: 'Konsultatsiya', date_from: '', date_to: '', notes: '' })

async function load() {
  loading.value = true
  error.value = false
  try {
    entries.value = (await api.get('/waitlist')).data
  } catch (e) {
    entries.value = []
    error.value = true
    toast.error(e, "Kutish ro'yxatini yuklab bo'lmadi")
  } finally { loading.value = false }
}

async function add() {
  saving.value = true
  try {
    const patients = await fetchAll('/patients', { search: form.patient_name })
    const patient = patients.find(p => p.name.toLowerCase() === form.patient_name.trim().toLowerCase())
    if (!patient) { toast.error(`"${form.patient_name}" nomli bemor topilmadi`); return }
    await api.post('/waitlist', {
      patient_id: patient.id, doctor: form.doctor, type: form.type,
      date_from: form.date_from || null, date_to: form.date_to || null, notes: form.notes || null,
    })
    Object.assign(form, { patient_name: '', notes: '', date_from: '', date_to: '' })
    toast.success("Kutish ro'yxatiga qo'shildi")
    await load()
  } catch (e) { toast.error(e, "Qo'shib bo'lmadi") } finally { saving.value = false }
}

async function toggleSuggest(e) {
  if (picking.value === e.id) { picking.value = null; return }
  picking.value = e.id
  suggestions.value = []
  sugLoading.value = true
  try {
    suggestions.value = (await api.get(`/waitlist/${e.id}/suggestions`, { params: { limit: 12 } })).data
  } catch (err) { toast.error(err, "Bo'sh vaqtlarni yuklab bo'lmadi") } finally { sugLoading.value = false }
}

async function book(e, s) {
  try {
    await api.post(`/waitlist/${e.id}/book`, { date: s.date, time: s.time })
    toast.success(`${e.patient_name} ${s.date} ${s.time} ga yozildi`)
    picking.value = null
    emit('booked')
    await load()
  } catch (err) {
    toast.error(err, "Yozib bo'lmadi")
    await toggleSuggest(e); await toggleSuggest(e) // vaqtlar band bo'lib qolgan bo'lishi mumkin: yangilash
  }
}

async function cancel(e) {
  try {
    await api.patch(`/waitlist/${e.id}`, { status: 'Cancelled' })
    toast.success('Kutish ro\'yxatidan olib tashlandi')
    await load()
  } catch (err) { toast.error(err, "Bekor qilib bo'lmadi") }
}

defineExpose({ reload: load })
onMounted(load)
</script>
