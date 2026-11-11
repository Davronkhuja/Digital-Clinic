<template>
  <div :class="['rounded-2xl border p-5 space-y-3', dark ? 'border-slate-800 bg-slate-800/20' : 'border-slate-200']">
    <div class="flex items-center justify-between">
      <h4 :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">Retsept (INN bo'yicha)</h4>
      <button type="button" class="flex items-center gap-1 text-xs text-cyan-500 hover:text-cyan-400 font-medium" @click="add"><Plus class="w-3.5 h-3.5" /> Dori qo'shish</button>
    </div>

    <ul v-if="existing.length" class="space-y-1.5">
      <li v-for="p in existing" :key="p.id" class="flex items-center gap-2 text-sm">
        <Pill class="w-3.5 h-3.5 text-cyan-500 flex-shrink-0" />
        <span class="flex-1" :class="dark ? 'text-slate-200' : 'text-slate-800'">{{ p.medication }}<span v-if="p.instructions" class="text-slate-400"> · {{ p.instructions }}</span></span>
        <button type="button" class="text-xs text-red-500 hover:underline" @click="$emit('cancel', p)">Bekor qilish</button>
      </li>
    </ul>

    <div v-for="(r, i) in rows" :key="i" class="grid grid-cols-6 gap-2 items-start">
      <div class="col-span-6 sm:col-span-2">
        <div class="relative">
          <input v-model="r.inn" class="input" placeholder="INN (masalan amlodipine)" autocomplete="off" @input="lookup(i)" @blur="hide(i)" />
          <ul v-if="r.open && r.options.length" class="absolute z-30 left-0 right-0 mt-1 max-h-44 overflow-y-auto rounded-xl border bg-white dark:bg-slate-800 dark:border-slate-700 shadow-xl text-sm">
            <li v-for="o in r.options" :key="o.inn"><button type="button" class="w-full text-left px-3 py-1.5 hover:bg-cyan-50 dark:hover:bg-slate-700" @mousedown.prevent="r.inn = o.inn; r.open = false">{{ o.inn }} <span class="text-xs text-slate-400">{{ o.group_uz }}</span></button></li>
          </ul>
        </div>
      </div>
      <input v-model="r.dose" class="input col-span-2 sm:col-span-1" placeholder="Doza: 5 mg" maxlength="100" />
      <select v-model="r.route" class="input col-span-2 sm:col-span-1"><option v-for="(label, k) in routes" :key="k" :value="k">{{ label }}</option></select>
      <input v-model="r.frequency" class="input col-span-2 sm:col-span-1" placeholder="kuniga 2 marta" maxlength="100" />
      <div class="col-span-6 sm:col-span-1 flex gap-1">
        <input v-model.number="r.duration_days" type="number" min="1" max="365" class="input" placeholder="kun" />
        <button type="button" class="p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg" @click="rows.splice(i, 1)"><X class="w-3.5 h-3.5" /></button>
      </div>
      <input v-model="r.instructions" class="input col-span-6" placeholder="Qo'shimcha ko'rsatma (ovqatdan keyin...)" />
    </div>
    <p v-if="!rows.length && !existing.length" :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">Dori qo'shilmagan</p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Plus, X, Pill } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useThemeStore } from '@/stores/theme'

const rows = defineModel('rows', { type: Array, default: () => [] })
defineProps({ existing: { type: Array, default: () => [] } })
defineEmits(['cancel'])
const theme = useThemeStore()
const dark = computed(() => theme.isDark)

const routes = {
  Oral: 'Ichga', Intravenous: 'Vena ichiga', Intramuscular: 'Mushak ichiga', Subcutaneous: 'Teri ostiga', Topical: 'Tashqi',
  Inhalation: 'Ingalyatsiya', Sublingual: 'Til ostiga', Rectal: "To'g'ri ichakka", Ophthalmic: "Ko'zga", Nasal: 'Burunga',
  Otic: 'Quloqqa', Vaginal: 'Qinga',
}
const add = () => rows.value.push({ inn: '', dose: '', route: 'Oral', frequency: '', duration_days: 7, instructions: '', options: [], open: false })
let timer
function lookup(i) {
  const r = rows.value[i]
  clearTimeout(timer)
  timer = setTimeout(async () => {
    try { r.options = (await api.get('/inn', { params: { search: r.inn, limit: 10 } })).data; r.open = true } catch { r.options = [] }
  }, 250)
}
function hide(i) { setTimeout(() => { if (rows.value[i]) rows.value[i].open = false }, 120) }
</script>
