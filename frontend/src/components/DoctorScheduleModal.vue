<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div :class="['w-full max-w-3xl rounded-2xl shadow-2xl overflow-hidden max-h-[92vh] flex flex-col', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
      <div :class="['flex items-center justify-between px-6 py-4 border-b flex-shrink-0', dark ? 'border-slate-800' : 'border-slate-200']">
        <div>
          <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Ish jadvali: {{ staff.name }}</h3>
          <p class="text-xs text-slate-400 mt-0.5">Vaqtlar klinika vaqti bo'yicha (Asia/Tashkent). Jadval bo'sh bo'lsa, shifokor cheklovsiz qabul qiladi.</p>
        </div>
        <button class="text-slate-400 hover:text-slate-600" @click="$emit('close')"><X class="w-5 h-5" /></button>
      </div>

      <div v-if="loading" class="p-12 text-center text-sm text-slate-400">Yuklanmoqda...</div>
      <div v-else-if="loadError" class="p-6"><EmptyState title="Jadvalni yuklab bo'lmadi" action-label="Qayta urinish" @action="load" /></div>
      <div v-else class="overflow-y-auto p-6 space-y-8">
        <section class="space-y-3">
          <h4 :class="['text-sm font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">Haftalik shablon</h4>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead><tr class="text-left text-xs text-slate-400"><th class="py-1 pr-3">Kun</th><th class="pr-3">Boshlanish</th><th class="pr-3">Tugash</th><th class="pr-3">Tanaffus dan</th><th>gacha</th></tr></thead>
              <tbody>
                <tr v-for="(d, i) in week" :key="i" :class="d.on ? '' : 'opacity-60'">
                  <td class="py-1 pr-3"><label class="flex items-center gap-2"><input v-model="d.on" type="checkbox" /> {{ dayNames[i] }}</label></td>
                  <td class="pr-3"><input v-model="d.start" type="time" class="input py-1" :disabled="!d.on" /></td>
                  <td class="pr-3"><input v-model="d.end" type="time" class="input py-1" :disabled="!d.on" /></td>
                  <td class="pr-3"><input v-model="d.bs" type="time" class="input py-1" :disabled="!d.on" /></td>
                  <td><input v-model="d.be" type="time" class="input py-1" :disabled="!d.on" /></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="flex items-center gap-3 flex-wrap">
            <button class="btn-secondary text-xs" type="button" @click="copyFirst">Birinchi yoqilgan kunni boshqa yoqilganlarga nusxalash</button>
            <button class="btn-primary text-sm ml-auto" :disabled="saving" @click="saveWeek"><Check class="w-4 h-4" /> Shablonni saqlash</button>
          </div>
        </section>

        <section class="space-y-3">
          <h4 :class="['text-sm font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">Standart qabul davomiyligi va kabinet</h4>
          <div class="flex items-end gap-3 flex-wrap">
            <div><label class="text-xs text-slate-400 block mb-1">Davomiylik (daq)</label><input v-model.number="slot" type="number" min="5" max="480" step="5" class="input w-28" /></div>
            <div class="flex-1 min-w-40">
              <label class="text-xs text-slate-400 block mb-1">Standart kabinet</label>
              <select v-model="roomId" class="input"><option value="">Belgilanmagan</option><option v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }}</option></select>
            </div>
            <button class="btn-secondary text-sm" :disabled="saving" @click="saveDefaults">Saqlash</button>
          </div>
        </section>

        <section class="space-y-3">
          <h4 :class="['text-sm font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">Istisnolar: ta'til, kasallik, dam olish, qo'shimcha ish kuni</h4>
          <form class="grid grid-cols-2 sm:grid-cols-6 gap-2 items-end" @submit.prevent="addException">
            <div class="col-span-2"><label class="text-xs text-slate-400 block mb-1">Turi</label>
              <select v-model="ex.kind" class="input"><option v-for="(label, k) in kinds" :key="k" :value="k">{{ label }}</option></select></div>
            <div><label class="text-xs text-slate-400 block mb-1">Sanadan</label><input v-model="ex.date_from" type="date" class="input" required /></div>
            <div v-if="ex.kind !== 'ExtraWork'"><label class="text-xs text-slate-400 block mb-1">Sanagacha</label><input v-model="ex.date_to" type="date" class="input" :min="ex.date_from" /></div>
            <template v-else>
              <div><label class="text-xs text-slate-400 block mb-1">Soat dan</label><input v-model="ex.start_time" type="time" class="input" required /></div>
              <div><label class="text-xs text-slate-400 block mb-1">gacha</label><input v-model="ex.end_time" type="time" class="input" required /></div>
            </template>
            <div class="col-span-2 sm:col-span-4"><input v-model="ex.note" class="input" placeholder="Izoh (ixtiyoriy)" maxlength="200" /></div>
            <button class="btn-primary text-sm" :disabled="saving"><Plus class="w-4 h-4" /> Qo'shish</button>
          </form>
          <p v-if="affected" class="text-sm text-amber-600">Diqqat: bu davrda ish vaqtidan tashqarida qolgan {{ affected }} ta rejalashtirilgan qabul bor. Ularni Uchrashuvlar bo'limida ko'chiring.</p>
          <EmptyState v-if="!exceptions.length" title="Istisno yo'q" />
          <ul v-else class="divide-y" :class="dark ? 'divide-slate-800' : 'divide-slate-100'">
            <li v-for="e in exceptions" :key="e.id" class="py-2 flex items-center gap-3 text-sm">
              <span class="badge-blue">{{ kinds[e.kind] }}</span>
              <span class="font-mono">{{ e.date_from }}<template v-if="e.date_to !== e.date_from"> – {{ e.date_to }}</template></span>
              <span v-if="e.start_time" class="font-mono text-slate-500">{{ e.start_time.slice(0, 5) }}–{{ e.end_time.slice(0, 5) }}</span>
              <span class="flex-1 text-slate-400 truncate">{{ e.note }}</span>
              <button class="text-red-500" title="Olib tashlash" @click="removeException(e)"><Trash2 class="w-4 h-4" /></button>
            </li>
          </ul>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { X, Check, Plus, Trash2 } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import EmptyState from '@/components/ui/EmptyState.vue'

const props = defineProps({ staff: { type: Object, required: true } })
const emit = defineEmits(['close', 'saved'])
const toast = useToast()
const theme = useThemeStore()
const dark = computed(() => theme.isDark)

const dayNames = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']
const kinds = { Vacation: "Ta'til", Sick: 'Kasallik', DayOff: 'Dam olish kuni', ExtraWork: "Qo'shimcha ish kuni" }
const hhmm = t => (t ? t.slice(0, 5) : '')

const loading = ref(true), loadError = ref(false), saving = ref(false)
const week = reactive(dayNames.map(() => ({ on: false, start: '09:00', end: '17:00', bs: '', be: '' })))
const exceptions = ref([])
const rooms = ref([])
const slot = ref(props.staff.slot_minutes || 30)
const roomId = ref(props.staff.default_room_id || '')
const affected = ref(0)
const emptyEx = () => ({ kind: 'Vacation', date_from: '', date_to: '', start_time: '', end_time: '', note: '' })
const ex = reactive(emptyEx())

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const [{ data }, r] = await Promise.all([api.get(`/staff/${props.staff.id}/schedule`), api.get('/rooms')])
    rooms.value = r.data
    week.forEach(d => { d.on = false })
    for (const d of data.days) {
      Object.assign(week[d.weekday], { on: true, start: hhmm(d.start_time), end: hhmm(d.end_time), bs: hhmm(d.break_start), be: hhmm(d.break_end) })
    }
    exceptions.value = data.exceptions
  } catch (e) {
    loadError.value = true
    toast.error(e, "Jadvalni yuklab bo'lmadi")
  } finally { loading.value = false }
}

function copyFirst() {
  const src = week.find(d => d.on)
  if (!src) return
  week.filter(d => d.on).forEach(d => Object.assign(d, { start: src.start, end: src.end, bs: src.bs, be: src.be }))
}

async function saveWeek() {
  saving.value = true
  const days = week.flatMap((d, weekday) => d.on ? [{
    weekday, start_time: d.start, end_time: d.end, break_start: d.bs || null, break_end: d.be || null,
  }] : [])
  try {
    await api.put(`/staff/${props.staff.id}/schedule`, { days })
    toast.success('Haftalik shablon saqlandi')
    emit('saved')
  } catch (e) { toast.error(e, "Shablonni saqlab bo'lmadi") } finally { saving.value = false }
}

async function saveDefaults() {
  saving.value = true
  try {
    await api.put(`/staff/${props.staff.id}`, { slot_minutes: slot.value, default_room_id: roomId.value || null })
    toast.success('Saqlandi')
    emit('saved')
  } catch (e) { toast.error(e, "Saqlab bo'lmadi") } finally { saving.value = false }
}

async function addException() {
  saving.value = true
  affected.value = 0
  const body = { kind: ex.kind, date_from: ex.date_from, note: ex.note || null }
  if (ex.kind === 'ExtraWork') Object.assign(body, { start_time: ex.start_time, end_time: ex.end_time })
  else body.date_to = ex.date_to || ex.date_from
  try {
    const { data } = await api.post(`/staff/${props.staff.id}/schedule/exceptions`, body)
    affected.value = data.affected_appointments.length
    Object.assign(ex, emptyEx())
    toast.success("Istisno qo'shildi")
    await load()
  } catch (e) { toast.error(e, "Istisnoni qo'shib bo'lmadi") } finally { saving.value = false }
}

async function removeException(e) {
  try {
    await api.delete(`/staff/${props.staff.id}/schedule/exceptions/${e.id}`)
    toast.success('Istisno olib tashlandi')
    await load()
  } catch (err) { toast.error(err, "Istisnoni olib tashlab bo'lmadi") }
}

onMounted(load)
</script>
