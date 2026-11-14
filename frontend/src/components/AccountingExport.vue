<template>
  <div class="card p-5 space-y-4" data-testid="accounting-export">
    <div>
      <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Buxgalteriya eksporti (1C uchun)</h3>
      <p class="text-xs text-slate-400 mt-0.5">Sotuvlar, to'lovlar, kassa smenalari, ombor harakatlari va shifokor foizlari. Ustun nomlari va formati Sozlamalar > Eksport da tahrirlanadi.</p>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-6 gap-3 items-end">
      <div class="col-span-2"><label class="text-xs text-slate-400 block mb-1">Ma'lumot</label>
        <select v-model="dataset" class="input" data-testid="exp-dataset"><option v-for="d in datasets" :key="d.name" :value="d.name">{{ d.title }}</option></select></div>
      <div><label class="text-xs text-slate-400 block mb-1">Dan</label><input v-model="from" type="date" class="input" data-testid="exp-from" /></div>
      <div><label class="text-xs text-slate-400 block mb-1">Gacha</label><input v-model="to" type="date" class="input" data-testid="exp-to" /></div>
      <div><label class="text-xs text-slate-400 block mb-1">Format</label>
        <select v-model="format" class="input" data-testid="exp-format"><option value="xlsx">Excel (.xlsx)</option><option value="csv">CSV</option></select></div>
      <button class="btn-primary" :disabled="busy" data-testid="exp-download" @click="download"><FileDown class="w-4 h-4" /> Yuklab olish</button>
    </div>
    <label v-if="auth.can('branches:all')" class="flex items-center gap-2 text-sm"><input v-model="allBranches" type="checkbox" /> Hamma filial birga</label>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { FileDown } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'

const toast = useToast(), theme = useThemeStore(), auth = useAuthStore()
const dark = computed(() => theme.isDark)
const datasets = ref([]), dataset = ref('sales'), format = ref('xlsx'), busy = ref(false), allBranches = ref(false)
const iso = d => d.toISOString().slice(0, 10)
const to = ref(iso(new Date())), from = ref(iso(new Date(Date.now() - 29 * 864e5)))

async function download() {
  busy.value = true
  try {
    const { data } = await api.get(`/exports/${dataset.value}`, { params: { format: format.value, date_from: from.value, date_to: to.value, ...(allBranches.value ? { all_branches: true } : {}) }, responseType: 'blob' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(data); a.download = `${dataset.value}_${from.value}_${to.value}.${format.value}`
    document.body.appendChild(a); a.click(); a.remove()
    toast.success('Fayl yuklandi')
  } catch (e) { toast.error(e, "Eksportni yuklab bo'lmadi") } finally { busy.value = false }
}
onMounted(async () => {
  try { datasets.value = (await api.get('/settings/exports')).data } catch { datasets.value = [] }
})
</script>
