<template>
  <div class="card p-5 space-y-4 max-w-xl">
    <div>
      <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Moliya sozlamalari</h3>
      <p class="text-xs text-slate-400 mt-0.5">O'zgarish faqat keyingi hisob-faktura va hisoblarga ta'sir qiladi; yozilganlari o'zgarmaydi.</p>
    </div>
    <p v-if="error" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <template v-else>
      <div>
        <label class="text-sm font-medium block mb-1" :class="dark ? 'text-slate-300' : 'text-slate-700'">Kassir chegirma limiti (%)</label>
        <input v-model.number="form.discount_limit_percent" type="number" min="0" max="100" step="0.01" class="input w-40" />
        <p class="text-xs text-slate-400 mt-1">Chegirma ruxsati (finance:discount) bor kassir shu foizgacha chegirma bera oladi (qator va umumiy chegirma birgalikda). Undan oshig'i uchun "Limitdan ortiq chegirma" ruxsati (admin) kerak. Sabab majburiy, hammasi auditda.</p>
      </div>
      <div class="flex justify-end"><button class="btn-primary text-sm" :disabled="saving" @click="save">Saqlash</button></div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'

const toast = useToast()
const theme = useThemeStore()
const dark = computed(() => theme.isDark)
const form = reactive({ discount_limit_percent: 10 })
const error = ref(false), saving = ref(false)

async function load() {
  error.value = false
  try { Object.assign(form, (await api.get('/settings/finance')).data) } catch (e) { error.value = true; toast.error(e, "Sozlamalarni yuklab bo'lmadi") }
}
async function save() {
  saving.value = true
  try { Object.assign(form, (await api.put('/settings/finance', { ...form })).data); toast.success('Saqlandi') } catch (e) { toast.error(e, "Saqlab bo'lmadi") } finally { saving.value = false }
}
onMounted(load)
</script>
