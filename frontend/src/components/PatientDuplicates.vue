<template>
  <div>
    <div v-if="loading" class="p-12 text-center">
      <div class="animate-spin w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto mb-3"></div>
      <p class="text-slate-400 text-sm">Yuklanmoqda...</p>
    </div>
    <EmptyState v-else-if="loadError" title="Dublikatlarni yuklab bo'lmadi" description="Server bilan aloqa o'rnatilmadi. Qayta urinib ko'ring." action-label="Qayta urinish" @action="load" />
    <EmptyState v-else-if="groups.length === 0" title="Dublikat topilmadi" description="Bir xil ism va telefon yoki tug'ilgan sanali faol bemorlar yo'q" />

    <div v-else class="grid lg:grid-cols-[18rem_1fr] gap-0">
      <ul :class="['border-b lg:border-b-0 lg:border-r max-h-[32rem] overflow-y-auto', dark ? 'border-slate-800' : 'border-slate-100']">
        <li v-for="(g, i) in groups" :key="i">
          <button :class="['w-full text-left px-4 py-3 border-b transition-colors', dark ? 'border-slate-800 hover:bg-slate-800/60' : 'border-slate-100 hover:bg-slate-50', i === current ? (dark ? 'bg-slate-800' : 'bg-cyan-50') : '']" @click="select(i)">
            <p :class="['font-medium text-sm', dark ? 'text-slate-200' : 'text-slate-900']">{{ g.patients[0].name }}</p>
            <p class="text-xs text-slate-400 mt-0.5">{{ g.patients.length }} ta yozuv</p>
            <div class="flex gap-1 mt-1.5 flex-wrap">
              <span v-for="r in g.reasons" :key="r" class="badge-blue">{{ reasonLabel[r] || r }}</span>
            </div>
          </button>
        </li>
      </ul>

      <div v-if="group" class="p-4 overflow-x-auto">
        <p :class="['text-sm mb-3', dark ? 'text-slate-400' : 'text-slate-500']">Asosiy yozuvni tanlang: boshqalarning uchrashuv, EMR, retsept va to'lovlari unga ko'chiriladi, o'zlari faolsizlantiriladi (o'chirilmaydi).</p>
        <table class="table">
          <thead>
            <tr>
              <th></th>
              <th v-for="p in group.patients" :key="p.id">
                <label class="flex items-center gap-2 cursor-pointer">
                  <input type="radio" name="primary" :value="p.id" v-model="primaryId" />
                  <span>{{ primaryId === p.id ? 'Asosiy' : 'Dublikat' }}</span>
                </label>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="f in fields" :key="f.key">
              <td :class="['text-xs font-medium', dark ? 'text-slate-400' : 'text-slate-500']">{{ f.label }}</td>
              <td v-for="p in group.patients" :key="p.id" :class="['text-sm', differs(f.key) ? 'font-semibold text-amber-600' : '', dark ? 'text-slate-300' : 'text-slate-700']">
                {{ show(p, f.key) }}
              </td>
            </tr>
            <tr>
              <td></td>
              <td v-for="p in group.patients" :key="p.id">
                <RouterLink :to="`/patients/${p.id}`" class="text-xs text-cyan-600 hover:underline">Profilni ochish</RouterLink>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="mt-4 flex justify-end">
          <button class="btn-primary" :disabled="!primaryId" @click="confirming = true"><GitMerge class="w-4 h-4" /> Birlashtirish</button>
        </div>
      </div>
    </div>

    <div v-if="confirming" class="modal-overlay" @click.self="confirming = false">
      <div :class="['w-full max-w-md rounded-2xl shadow-2xl p-6', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
        <h3 :class="['font-heading font-semibold mb-2', dark ? 'text-white' : 'text-slate-900']">Birlashtirishni tasdiqlang</h3>
        <p :class="['text-sm', dark ? 'text-slate-400' : 'text-slate-600']">
          «{{ primary?.name }}» asosiy bo'ladi. Qolgan {{ group.patients.length - 1 }} ta yozuvning ma'lumotlari unga ko'chiriladi va ular faolsizlantiriladi. Buni oddiy tarzda qaytarib bo'lmaydi.
        </p>
        <div class="flex justify-end gap-2 mt-5">
          <button class="btn-secondary" :disabled="merging" @click="confirming = false">Bekor qilish</button>
          <button class="btn-primary" :disabled="merging" @click="merge">{{ merging ? 'Birlashtirilmoqda...' : 'Birlashtirish' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { GitMerge } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import EmptyState from '@/components/ui/EmptyState.vue'

const emit = defineEmits(['merged'])
const theme = useThemeStore()
const dark = computed(() => theme.isDark)
const toast = useToast()

const groups = ref([])
const current = ref(0)
const primaryId = ref(null)
const loading = ref(true)
const loadError = ref(false)
const confirming = ref(false)
const merging = ref(false)

const reasonLabel = { phone: 'Ism + telefon', birth_date: "Ism + tug'ilgan sana", pinfl: 'PINFL' }
const fields = [
  { key: 'name', label: 'Ism' }, { key: 'phone', label: 'Telefon' }, { key: 'birth_date', label: "Tug'ilgan sana" },
  { key: 'gender', label: 'Jins' }, { key: 'pinfl', label: 'PINFL' }, { key: 'blood_type', label: 'Qon guruhi' },
  { key: 'address', label: 'Manzil' }, { key: 'allergies', label: 'Allergiya' }, { key: 'doctor', label: 'Shifokor' },
  { key: 'last_visit', label: "So'nggi tashrif" }, { key: 'created_at', label: "Qo'shilgan sana" },
]

const group = computed(() => groups.value[current.value])
const primary = computed(() => group.value?.patients.find(p => p.id === primaryId.value))

function show(p, key) {
  const v = p[key]
  if (key === 'gender') return { male: 'Erkak', female: 'Ayol', other: 'Boshqa' }[v] || '—'
  return v || '—'
}
function differs(key) {
  return new Set(group.value.patients.map(p => show(p, key))).size > 1
}
function select(i) {
  current.value = i
  primaryId.value = groups.value[i].patients[0].id // eng eski yozuv standart asosiy
}

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const { data } = await api.get('/patients/duplicates')
    groups.value = data
    current.value = 0
    if (data.length) select(0)
  } catch (e) {
    groups.value = []
    loadError.value = true
    toast.error(e, "Dublikatlarni yuklab bo'lmadi")
  } finally { loading.value = false }
}

async function merge() {
  merging.value = true
  try {
    for (const p of group.value.patients.filter(x => x.id !== primaryId.value)) {
      await api.post(`/patients/${primaryId.value}/merge`, { source_id: p.id })
    }
    toast.success('Bemorlar birlashtirildi')
    confirming.value = false
    emit('merged')
    await load()
  } catch (e) {
    toast.error(e, "Birlashtirib bo'lmadi")
    confirming.value = false
    await load()
  } finally { merging.value = false }
}

onMounted(load)
</script>
