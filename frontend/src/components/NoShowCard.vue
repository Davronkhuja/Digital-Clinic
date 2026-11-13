<template>
  <div class="card p-5 space-y-3">
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <div>
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Kelmay qolish ulushi (haftalik)</h3>
        <p class="text-xs text-slate-400">no-show / (yakunlangan + kelmagan), eslatma yuborilgan va yuborilmagan qabullar kesimida</p>
      </div>
      <div v-if="data" class="text-right">
        <p class="text-3xl font-bold" :class="rateClass(data.current.rate)">{{ fmt(data.current.rate) }}</p>
        <p class="text-xs text-slate-400">joriy hafta · {{ data.current.no_show }} / {{ data.current.total }}</p>
      </div>
    </div>
    <p v-if="error" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <div v-else-if="data" class="table-container rounded-none border-0">
      <table class="table text-sm">
        <thead><tr><th>Hafta</th><th class="text-right">Jami</th><th class="text-right">Kelmadi</th><th class="text-right">Ulush</th><th class="text-right">Eslatma yuborilgan</th><th class="text-right">Yuborilmagan</th></tr></thead>
        <tbody>
          <tr v-for="w in [...data.weeks].reverse()" :key="w.week_start">
            <td class="font-mono text-xs">{{ w.week_start }}</td><td class="text-right">{{ w.total }}</td><td class="text-right">{{ w.no_show }}</td>
            <td class="text-right font-semibold" :class="rateClass(w.rate)">{{ fmt(w.rate) }}</td>
            <td class="text-right text-emerald-600">{{ fmt(w.reminded.rate) }} <span class="text-xs text-slate-400">({{ w.reminded.no_show }}/{{ w.reminded.total }})</span></td>
            <td class="text-right text-amber-600">{{ fmt(w.not_reminded.rate) }} <span class="text-xs text-slate-400">({{ w.not_reminded.no_show }}/{{ w.not_reminded.total }})</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'

const toast = useToast(), theme = useThemeStore()
const dark = computed(() => theme.isDark)
const data = ref(null), error = ref(false)
const fmt = r => (r == null ? '—' : `${r}%`)
const rateClass = r => (r == null ? 'text-slate-400' : r >= 20 ? 'text-red-500' : r >= 10 ? 'text-amber-600' : 'text-emerald-600')

async function load() {
  error.value = false
  try { data.value = (await api.get('/analytics/no-show', { params: { weeks: 8 } })).data } catch (e) { error.value = true; toast.error(e, "Kelmay qolish ulushini yuklab bo'lmadi") }
}
onMounted(load)
</script>
