<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div :class="['w-full max-w-3xl rounded-2xl shadow-2xl max-h-[92vh] flex flex-col', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
      <div :class="['flex items-center justify-between px-6 py-4 border-b flex-shrink-0', dark ? 'border-slate-800' : 'border-slate-200']">
        <div>
          <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Ko'rik kartasi (DMED tartibida)</h3>
          <p class="text-xs text-slate-400 mt-0.5">DMED bilan API yo'q: maydonlarni nusxalab DMED ga kiriting, so'ng "ko'chirildi" deb belgilang.</p>
        </div>
        <button class="text-slate-400" @click="$emit('close')"><X class="w-5 h-5" /></button>
      </div>

      <p v-if="loading" class="p-10 text-center text-sm text-slate-400">Yuklanmoqda...</p>
      <div v-else-if="error" class="p-6"><EmptyState title="Kartani yuklab bo'lmadi" action-label="Qayta urinish" @action="load" /></div>
      <div v-else class="overflow-y-auto p-6 space-y-6">
        <section v-for="g in groups" :key="g.title">
          <h4 :class="['text-xs uppercase tracking-wider font-semibold mb-2', dark ? 'text-slate-500' : 'text-slate-400']">{{ g.title }}</h4>
          <div v-for="f in g.fields" :key="f.key" :class="['flex items-start gap-3 py-2 border-b', dark ? 'border-slate-800' : 'border-slate-100']">
            <div class="w-36 flex-shrink-0 text-xs text-slate-400 pt-0.5">{{ f.label }}</div>
            <div class="flex-1 text-sm whitespace-pre-line" :class="[f.value ? (dark ? 'text-slate-200' : 'text-slate-800') : 'text-slate-400']">
              {{ f.value || '—' }}
              <p v-if="f.key === 'diagnosis' && card.icd_code" class="mt-1 font-mono text-xs text-cyan-600">
                MKB-10: {{ card.icd_code }}<span v-if="card.icd_name"> — {{ card.icd_name }}</span>
                <span v-if="card.icd_verified === false" class="ml-2 badge-yellow text-[10px]" title="Starter namuna: tasdiqlanmagan">namuna</span>
                <button class="ml-2 inline-flex items-center text-slate-400 hover:text-cyan-600" title="MKB-10 kodini nusxalash" @click="copy(card.icd_code, 'MKB-10 kodi')"><Copy class="w-3.5 h-3.5" /></button>
              </p>
            </div>
            <button v-if="f.value" class="text-slate-400 hover:text-cyan-600 flex-shrink-0" title="Nusxalash" @click="copy(f.value, f.label)"><Copy class="w-4 h-4" /></button>
          </div>
        </section>

        <section v-if="card.prescriptions.length">
          <h4 :class="['text-xs uppercase tracking-wider font-semibold mb-2', dark ? 'text-slate-500' : 'text-slate-400']">Retsept (INN)</h4>
          <div v-for="(p, i) in card.prescriptions" :key="i" :class="['py-2 border-b text-sm', dark ? 'border-slate-800' : 'border-slate-100']">
            <div class="flex items-center gap-2 flex-wrap">
              <button class="font-semibold text-cyan-600 hover:underline" title="INN ni nusxalash" @click="copy(p.inn, 'INN')">{{ p.inn }}</button>
              <button v-if="p.dose" class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-xs" title="Dozani nusxalash" @click="copy(p.dose, 'Doza')">{{ p.dose }}</button>
              <span class="text-xs text-slate-500">{{ p.route }} · {{ p.frequency }} · {{ p.duration_days }} kun</span>
              <span class="flex-1"></span>
              <button class="text-slate-400 hover:text-cyan-600" title="Butun qatorni nusxalash" @click="copy(p.text, 'Retsept')"><Copy class="w-4 h-4" /></button>
            </div>
            <p v-if="p.instructions" class="text-xs text-slate-400 mt-0.5">{{ p.instructions }}</p>
          </div>
        </section>

        <section v-if="card.lab_results.length">
          <h4 :class="['text-xs uppercase tracking-wider font-semibold mb-2', dark ? 'text-slate-500' : 'text-slate-400']">Laboratoriya natijalari</h4>
          <div v-for="(l, i) in card.lab_results" :key="i" class="flex gap-3 py-1 text-sm">
            <span class="flex-1">{{ l.name }}</span>
            <span :class="['font-mono', l.flag === 'High' || l.flag === 'Low' ? 'text-red-600 font-semibold' : '']">{{ l.value }} {{ l.unit }}</span>
            <span class="w-24 text-xs text-slate-400 font-mono">{{ l.reference || '—' }}<span v-if="l.ref_verified === false" class="ml-1 badge-yellow text-[9px]" title="Namuna me'yor">namuna</span></span>
          </div>
        </section>
      </div>

      <div v-if="card" :class="['flex items-center gap-3 flex-wrap px-6 py-4 border-t flex-shrink-0', dark ? 'border-slate-800' : 'border-slate-200']">
        <label v-if="auth.can('emr:write')" class="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" :checked="!!card.dmed_copied_at" :disabled="marking" @change="toggleMark($event.target.checked)" />
          DMED ga ko'chirildi
        </label>
        <span v-else-if="card.dmed_copied_at" class="badge-green">DMED ga ko'chirildi</span>
        <span v-if="card.dmed_copied_at" class="text-xs text-slate-400">{{ card.dmed_copied_at.slice(0, 10) }} · {{ card.dmed_copied_by }}</span>
        <span class="flex-1"></span>
        <button class="btn-secondary text-sm" @click="copy(allText, 'Butun karta')"><Copy class="w-4 h-4" /> Hammasini nusxalash</button>
        <button class="btn-primary text-sm" @click="print"><Printer class="w-4 h-4" /> Chop etish</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { X, Copy, Printer } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/ui/EmptyState.vue'

const props = defineProps({ recordId: { type: String, required: true } })
const emit = defineEmits(['close', 'marked'])
const toast = useToast()
const theme = useThemeStore()
const auth = useAuthStore()
const dark = computed(() => theme.isDark)

const card = ref(null), loading = ref(true), error = ref(false), marking = ref(false)
const groups = computed(() => card.value ? [
  { title: 'Bemor', fields: card.value.patient }, { title: 'Murojaat', fields: card.value.visit }, { title: "Ko'rik", fields: card.value.sections },
] : [])
const allText = computed(() => {
  if (!card.value) return ''
  const c = card.value
  const lines = [...c.patient, ...c.visit, ...c.sections].filter(f => f.value).map(f => `${f.label}: ${f.value}`)
  if (c.icd_code) lines.push(`MKB-10: ${c.icd_code}${c.icd_name ? ' — ' + c.icd_name : ''}`)
  c.prescriptions.forEach(p => lines.push(`Retsept: ${p.text}${p.instructions ? ' (' + p.instructions + ')' : ''}`))
  return lines.join('\n')
})

async function load() {
  loading.value = true
  error.value = false
  try { card.value = (await api.get(`/emr/${props.recordId}/card`)).data } catch (e) {
    error.value = true
    toast.error(e, "Kartani yuklab bo'lmadi")
  } finally { loading.value = false }
}
async function copy(text, what) {
  try {
    await navigator.clipboard.writeText(text)
    toast.success(`${what} nusxalandi`)
  } catch { toast.error("Nusxalab bo'lmadi: brauzer ruxsat bermadi") }
}
async function toggleMark(copied) {
  marking.value = true
  try {
    card.value = (await api.post(`/emr/${props.recordId}/dmed-mark`, { copied })).data
    emit('marked', card.value.dmed_copied_at)
  } catch (e) { toast.error(e, "Belgini saqlab bo'lmadi"); await load() } finally { marking.value = false }
}
async function print() {
  try {
    const { data } = await api.get(`/emr/${props.recordId}/card/pdf`, { responseType: 'blob' })
    window.open(URL.createObjectURL(data), '_blank')
  } catch (e) { toast.error(e, "PDF ochib bo'lmadi") }
}
onMounted(load)
</script>
