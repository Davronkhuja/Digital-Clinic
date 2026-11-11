<template>
  <div class="grid lg:grid-cols-2 gap-6">
    <section class="card p-5 space-y-4">
      <div>
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Kabinetlar</h3>
        <p class="text-xs text-slate-400 mt-0.5">Bir kabinetda bir vaqtda bitta qabul. Ishlatilgan kabinet o'chirilmaydi, faolsizlantiriladi.</p>
      </div>
      <form class="flex gap-2" @submit.prevent="addRoom">
        <input v-model="roomForm.name" class="input w-24" placeholder="101" required maxlength="60" />
        <input v-model="roomForm.description" class="input flex-1" placeholder="Izoh (ixtiyoriy)" maxlength="200" />
        <button class="btn-primary" :disabled="savingRoom"><Plus class="w-4 h-4" /></button>
      </form>
      <p v-if="roomsError" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="loadRooms">Qayta urinish</button></p>
      <EmptyState v-else-if="!rooms.length" title="Kabinet yo'q" description="Birinchi kabinetni qo'shing" />
      <ul v-else class="divide-y" :class="dark ? 'divide-slate-800' : 'divide-slate-100'">
        <li v-for="r in rooms" :key="r.id" class="py-2.5 flex items-center gap-3">
          <template v-if="editRoom?.id === r.id">
            <input v-model="editRoom.name" class="input w-24" maxlength="60" />
            <input v-model="editRoom.description" class="input flex-1" maxlength="200" />
            <button class="text-emerald-500" title="Saqlash" @click="saveRoom"><Check class="w-4 h-4" /></button>
            <button class="text-slate-400" title="Bekor" @click="editRoom = null"><X class="w-4 h-4" /></button>
          </template>
          <template v-else>
            <span :class="['font-mono font-semibold w-24', r.is_active ? '' : 'line-through text-slate-400', dark ? 'text-slate-200' : 'text-slate-800']">{{ r.name }}</span>
            <span class="flex-1 text-sm text-slate-500">{{ r.description || '—' }}</span>
            <span :class="r.is_active ? 'badge-green' : 'badge-slate'">{{ r.is_active ? 'Faol' : 'Nofaol' }}</span>
            <button class="text-slate-400 hover:text-cyan-600" title="Tahrirlash" @click="editRoom = { ...r }"><Pencil class="w-4 h-4" /></button>
            <button v-if="!r.is_active" class="text-xs text-cyan-600" @click="patchRoom(r, { is_active: true })">Faollashtirish</button>
            <button v-else class="text-red-500" title="O'chirish yoki faolsizlantirish" @click="removeRoom(r)"><Trash2 class="w-4 h-4" /></button>
          </template>
        </li>
      </ul>
    </section>

    <section class="card p-5 space-y-4">
      <div>
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Qabul turlari va davomiyligi</h3>
        <p class="text-xs text-slate-400 mt-0.5">Davomiylik: tur bo'yicha, bo'lmasa shifokorning standart davomiyligi (Xodimlar), bo'lmasa 30 daqiqa.</p>
      </div>
      <form class="flex gap-2" @submit.prevent="addType">
        <input v-model="typeForm.name" class="input flex-1" placeholder="Tur nomi" required minlength="2" maxlength="60" />
        <input v-model.number="typeForm.duration_min" type="number" min="5" max="480" step="5" class="input w-24" required />
        <button class="btn-primary" :disabled="savingType"><Plus class="w-4 h-4" /></button>
      </form>
      <p v-if="typesError" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="loadTypes">Qayta urinish</button></p>
      <EmptyState v-else-if="!types.length" title="Qabul turi yo'q" description="Birinchi turni qo'shing" />
      <ul v-else class="divide-y" :class="dark ? 'divide-slate-800' : 'divide-slate-100'">
        <li v-for="t in types" :key="t.id" class="py-2.5 flex items-center gap-3">
          <template v-if="editType?.id === t.id">
            <input v-model="editType.name" class="input flex-1" maxlength="60" />
            <input v-model.number="editType.duration_min" type="number" min="5" max="480" step="5" class="input w-24" />
            <button class="text-emerald-500" title="Saqlash" @click="saveType"><Check class="w-4 h-4" /></button>
            <button class="text-slate-400" title="Bekor" @click="editType = null"><X class="w-4 h-4" /></button>
          </template>
          <template v-else>
            <span :class="['flex-1 font-medium', t.is_active ? '' : 'line-through text-slate-400', dark ? 'text-slate-200' : 'text-slate-800']">{{ t.name }}</span>
            <span class="text-sm font-mono text-slate-500">{{ t.duration_min }} daq</span>
            <span :class="t.is_active ? 'badge-green' : 'badge-slate'">{{ t.is_active ? 'Faol' : 'Nofaol' }}</span>
            <button class="text-slate-400 hover:text-cyan-600" title="Tahrirlash" @click="editType = { ...t }"><Pencil class="w-4 h-4" /></button>
            <button v-if="!t.is_active" class="text-xs text-cyan-600" @click="patchType(t, { is_active: true })">Faollashtirish</button>
            <button v-else class="text-red-500" title="O'chirish yoki faolsizlantirish" @click="removeType(t)"><Trash2 class="w-4 h-4" /></button>
          </template>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Check, X, Pencil, Trash2 } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast()
const theme = useThemeStore()
const dark = computed(() => theme.isDark)

// Kabinetlar
const rooms = ref([]), roomsError = ref(false), savingRoom = ref(false), editRoom = ref(null)
const roomForm = reactive({ name: '', description: '' })

async function loadRooms() {
  roomsError.value = false
  try {
    rooms.value = (await api.get('/rooms', { params: { include_inactive: true } })).data
  } catch (e) {
    rooms.value = []
    roomsError.value = true
    toast.error(e, "Kabinetlarni yuklab bo'lmadi")
  }
}
async function addRoom() {
  savingRoom.value = true
  try {
    await api.post('/rooms', { name: roomForm.name, description: roomForm.description || null })
    roomForm.name = ''; roomForm.description = ''
    toast.success("Kabinet qo'shildi")
    await loadRooms()
  } catch (e) { toast.error(e, "Kabinetni qo'shib bo'lmadi") } finally { savingRoom.value = false }
}
async function patchRoom(r, body) {
  try {
    await api.put(`/rooms/${r.id}`, body)
    await loadRooms()
  } catch (e) { toast.error(e, "Kabinetni o'zgartirib bo'lmadi") }
}
async function saveRoom() {
  await patchRoom(editRoom.value, { name: editRoom.value.name, description: editRoom.value.description || '' })
  editRoom.value = null
}
async function removeRoom(r) {
  try {
    const { data } = await api.delete(`/rooms/${r.id}`)
    toast.success(data.message)
    await loadRooms()
  } catch (e) { toast.error(e, "Kabinetni o'chirib bo'lmadi") }
}

// Qabul turlari
const types = ref([]), typesError = ref(false), savingType = ref(false), editType = ref(null)
const typeForm = reactive({ name: '', duration_min: 30 })

async function loadTypes() {
  typesError.value = false
  try {
    types.value = (await api.get('/appointment-types', { params: { include_inactive: true } })).data
  } catch (e) {
    types.value = []
    typesError.value = true
    toast.error(e, "Qabul turlarini yuklab bo'lmadi")
  }
}
async function addType() {
  savingType.value = true
  try {
    await api.post('/appointment-types', { name: typeForm.name, duration_min: typeForm.duration_min })
    typeForm.name = ''; typeForm.duration_min = 30
    toast.success("Qabul turi qo'shildi")
    await loadTypes()
  } catch (e) { toast.error(e, "Qabul turini qo'shib bo'lmadi") } finally { savingType.value = false }
}
async function patchType(t, body) {
  try {
    await api.put(`/appointment-types/${t.id}`, body)
    await loadTypes()
  } catch (e) { toast.error(e, "Qabul turini o'zgartirib bo'lmadi") }
}
async function saveType() {
  await patchType(editType.value, { name: editType.value.name, duration_min: editType.value.duration_min })
  editType.value = null
}
async function removeType(t) {
  try {
    const { data } = await api.delete(`/appointment-types/${t.id}`)
    toast.success(data.message)
    await loadTypes()
  } catch (e) { toast.error(e, "Qabul turini o'chirib bo'lmadi") }
}

onMounted(() => { loadRooms(); loadTypes() })
</script>
