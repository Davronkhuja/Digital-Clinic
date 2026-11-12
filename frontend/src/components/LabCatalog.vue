<template>
  <div class="card p-5 space-y-4 max-w-5xl">
    <div>
      <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Laboratoriya me'yorlari</h3>
      <p class="text-xs text-slate-400 mt-0.5">Me'yorlarni o'z analizatoringiz reagent yo'riqnomasiga moslang. "Namuna" belgisi starter (tasdiqlanmagan) qiymatlarda; tahrirlab saqlasangiz tasdiqlangan hisoblanadi. Yozilgan natijalar o'zgarmaydi.</p>
    </div>
    <input v-model="filter" class="input" placeholder="Tahlil qidirish..." />
    <p v-if="error" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <div v-for="t in shown" :key="t.id" :class="['border rounded-xl p-3', dark ? 'border-slate-800' : 'border-slate-200']">
      <div class="flex items-center gap-3 flex-wrap">
        <span :class="['font-medium', dark ? 'text-slate-200' : 'text-slate-800']">{{ t.name }}</span>
        <span class="font-mono text-xs text-slate-400">{{ t.code }} · {{ t.unit }}</span>
        <span v-if="!t.verified" class="badge-yellow text-[10px]">namuna</span>
        <span v-else class="badge-green text-[10px]" :title="t.source">tasdiqlangan</span>
        <span class="flex-1"></span>
        <button v-if="editing !== t.id" class="text-xs text-cyan-600 hover:underline" @click="edit(t)">Me'yorni tahrirlash</button>
      </div>
      <ul v-if="editing !== t.id" class="mt-2 text-xs text-slate-500 space-y-0.5">
        <li v-for="r in t.ranges" :key="r.id">{{ sexLabel[r.sex || ''] }}{{ ageText(r) }}: <span class="font-mono">{{ rangeText(r) }}</span>
          <span v-if="!r.verified" class="ml-1 badge-yellow text-[9px]">namuna</span></li>
      </ul>
      <div v-else class="mt-3 space-y-2">
        <div v-for="(r, i) in draft.ranges" :key="i" class="grid grid-cols-12 gap-2 items-center">
          <select v-model="r.sex" class="input col-span-2 py-1"><option :value="null">Ikkala jins</option><option value="male">Erkak</option><option value="female">Ayol</option></select>
          <input v-model.number="r.age_min" type="number" min="0" max="150" class="input col-span-1 py-1" placeholder="yosh dan" />
          <input v-model.number="r.age_max" type="number" min="0" max="150" class="input col-span-1 py-1" placeholder="gacha" />
          <input v-model.number="r.low" type="number" step="any" class="input col-span-2 py-1" placeholder="past chegara" />
          <input v-model.number="r.high" type="number" step="any" class="input col-span-2 py-1" placeholder="yuqori chegara" />
          <input v-model="r.source" class="input col-span-3 py-1" placeholder="Manba (analizator...)" />
          <button class="text-red-500 col-span-1" title="Olib tashlash" @click="draft.ranges.splice(i, 1)"><Trash2 class="w-4 h-4" /></button>
        </div>
        <button class="text-xs text-cyan-600" @click="draft.ranges.push(blank())"><Plus class="w-3.5 h-3.5 inline" /> Me'yor qo'shish</button>
        <input v-model="draft.source" class="input" placeholder="Tahlil manbasi (masalan: Mindray BS-240 reagent yo'riqnomasi)" />
        <div class="flex justify-end gap-2">
          <button class="btn-secondary text-sm" @click="editing = null">Bekor qilish</button>
          <button class="btn-primary text-sm" :disabled="saving" @click="save(t)">Saqlash</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'

const toast = useToast()
const theme = useThemeStore()
const dark = computed(() => theme.isDark)
const sexLabel = { '': 'Ikkala jins', male: 'Erkak', female: 'Ayol' }

const tests = ref([]), error = ref(false), filter = ref(''), editing = ref(null), saving = ref(false)
const draft = reactive({ ranges: [], source: '' })
const shown = computed(() => tests.value.filter(t => !filter.value || (t.name + t.code).toLowerCase().includes(filter.value.toLowerCase())))
const blank = () => ({ sex: null, age_min: null, age_max: null, low: null, high: null, source: '', verified: true })
const ageText = r => (r.age_min != null || r.age_max != null ? `, ${r.age_min ?? 0}-${r.age_max ?? '…'} yosh` : '')
const rangeText = r => (r.low != null && r.high != null ? `${r.low} - ${r.high}` : r.high != null ? `<= ${r.high}` : `>= ${r.low}`)

async function load() {
  error.value = false
  try { tests.value = (await api.get('/lab/tests', { params: { include_inactive: true } })).data } catch (e) {
    tests.value = []; error.value = true; toast.error(e, "Katalogni yuklab bo'lmadi")
  }
}
function edit(t) {
  editing.value = t.id
  draft.source = t.source && t.verified ? t.source : ''
  draft.ranges = t.ranges.map(r => ({ sex: r.sex, age_min: r.age_min, age_max: r.age_max, low: r.low, high: r.high, source: r.verified ? r.source : '', verified: r.verified }))
}
async function save(t) {
  saving.value = true
  // tahrirlab saqlangan me'yor tasdiqlangan hisoblanadi (administrator ko'rib chiqqan)
  const ranges = draft.ranges.map(r => ({ sex: r.sex || null, age_min: r.age_min ?? null, age_max: r.age_max ?? null, low: r.low ?? null, high: r.high ?? null, source: r.source || null, verified: true }))
  try {
    await api.put(`/lab/tests/${t.id}`, { ranges, verified: true, source: draft.source || null })
    toast.success("Me'yor saqlandi")
    editing.value = null
    await load()
  } catch (e) { toast.error(e, "Saqlab bo'lmadi") } finally { saving.value = false }
}
onMounted(load)
</script>
