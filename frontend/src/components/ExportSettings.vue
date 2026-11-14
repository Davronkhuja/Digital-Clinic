<template>
  <div class="card p-5 space-y-6 max-w-4xl" data-testid="export-settings">
    <div>
      <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Eksport (buxgalteriya / 1C)</h3>
      <p class="text-xs text-slate-400 mt-0.5">Rasmiy 1C formati hujjati yo'q: ustun nomi, tartibi va format shu yerda sozlanadi (keyin buxgalter bilan 1C ga moslanadi).</p>
    </div>

    <section class="space-y-2">
      <h4 class="text-sm font-semibold">Format</h4>
      <div class="grid grid-cols-3 gap-3 max-w-xl">
        <div><label class="text-xs text-slate-400 block mb-1">Sana</label>
          <select v-model="fmt.date_format" class="input" data-testid="fmt-date"><option value="iso">2026-11-30</option><option value="dmy">30.11.2026</option></select></div>
        <div><label class="text-xs text-slate-400 block mb-1">O'nlik ajratgich</label>
          <select v-model="fmt.decimal_separator" class="input" data-testid="fmt-decimal"><option value=".">nuqta (1234.50)</option><option value=",">vergul (1234,50)</option></select></div>
        <div><label class="text-xs text-slate-400 block mb-1">CSV ustun ajratgichi</label>
          <select v-model="fmt.csv_delimiter" class="input" data-testid="fmt-delim"><option value=";">nuqtali vergul ( ; )</option><option value=",">vergul ( , )</option><option value="tab">tab</option></select></div>
      </div>
      <button class="btn-secondary text-sm" :disabled="busy" data-testid="fmt-save" @click="saveFormat">Formatni saqlash</button>
    </section>

    <section class="space-y-3">
      <div class="flex gap-2 items-center flex-wrap">
        <h4 class="text-sm font-semibold">Ustun xaritasi</h4>
        <select v-model="current" class="input w-auto text-sm" data-testid="map-dataset"><option v-for="d in datasets" :key="d.name" :value="d.name">{{ d.title }}</option></select>
        <span v-if="ds?.customized" class="badge-blue">Sozlangan</span>
      </div>
      <div class="table-container rounded-none border-0">
        <table class="table text-sm"><thead><tr><th>Yoqilgan</th><th>Standart nom</th><th>Eksportdagi sarlavha</th><th class="text-right">Tartib</th></tr></thead>
          <tbody><tr v-for="(c, i) in cols" :key="c.key">
            <td><input v-model="c.enabled" type="checkbox" /></td><td class="text-slate-500">{{ c.default_header }} <span class="font-mono text-xs text-slate-400">{{ c.key }}</span></td>
            <td><input v-model="c.header" class="input py-1" maxlength="80" data-testid="map-header" /></td>
            <td class="text-right whitespace-nowrap"><button class="px-2 text-slate-400 hover:text-cyan-600" :disabled="i === 0" @click="move(i, -1)">↑</button><button class="px-2 text-slate-400 hover:text-cyan-600" :disabled="i === cols.length - 1" @click="move(i, 1)">↓</button></td>
          </tr></tbody></table>
      </div>
      <div class="flex gap-2">
        <button class="btn-primary text-sm" :disabled="busy" data-testid="map-save" @click="saveMap">Xaritani saqlash</button>
        <button v-if="ds?.customized" class="btn-secondary text-sm" :disabled="busy" @click="resetMap">Standartga qaytarish</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'

const toast = useToast(), theme = useThemeStore()
const dark = computed(() => theme.isDark)
const datasets = ref([]), current = ref('sales'), cols = ref([]), busy = ref(false)
const fmt = reactive({ date_format: 'iso', decimal_separator: '.', csv_delimiter: ';' })
const ds = computed(() => datasets.value.find(d => d.name === current.value))

function pick() { cols.value = (ds.value?.columns || []).map(c => ({ ...c })) }
watch(current, pick)
async function load() {
  try {
    datasets.value = (await api.get('/settings/exports')).data
    Object.assign(fmt, (await api.get('/settings/export-format')).data)
    pick()
  } catch (e) { toast.error(e, "Eksport sozlamalarini yuklab bo'lmadi") }
}
function move(i, d) { const a = cols.value; [a[i], a[i + d]] = [a[i + d], a[i]] }
async function saveFormat() {
  busy.value = true
  try { await api.put('/settings/export-format', fmt); toast.success('Format saqlandi') } catch (e) { toast.error(e, "Formatni saqlab bo'lmadi") } finally { busy.value = false }
}
async function saveMap() {
  busy.value = true
  try {
    const { data } = await api.put(`/settings/exports/${current.value}`, { columns: cols.value.map(c => ({ key: c.key, header: c.header, enabled: c.enabled })) })
    datasets.value = datasets.value.map(d => (d.name === data.name ? data : d)); pick(); toast.success('Ustun xaritasi saqlandi')
  } catch (e) { toast.error(e, "Xaritani saqlab bo'lmadi") } finally { busy.value = false }
}
async function resetMap() {
  busy.value = true
  try {
    const { data } = await api.delete(`/settings/exports/${current.value}`)
    datasets.value = datasets.value.map(d => (d.name === data.name ? data : d)); pick(); toast.success('Standart ustunlar tiklandi')
  } catch (e) { toast.error(e, "Tiklab bo'lmadi") } finally { busy.value = false }
}
onMounted(load)
</script>
