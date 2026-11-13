<template>
  <div class="card p-5 space-y-5 max-w-3xl">
    <div>
      <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Xabarlar</h3>
      <p class="text-xs text-slate-400 mt-0.5">Shablonlar o'zbek (lotin) va rus tilida. Joy egalari: {clinic}, {patient}, {doctor}, {date}, {time}, {link}, {code}. SMS uchun lotin matnda oddiy apostrof (') ishlating.</p>
    </div>
    <div class="flex items-end gap-3 flex-wrap">
      <div><label class="text-xs text-slate-400 block mb-1">Tungi vaqt boshlanishi (soat)</label><input v-model.number="quiet.quiet_start_hour" type="number" min="0" max="23" class="input w-28" /></div>
      <div><label class="text-xs text-slate-400 block mb-1">Tugashi (soat)</label><input v-model.number="quiet.quiet_end_hour" type="number" min="0" max="23" class="input w-28" /></div>
      <button class="btn-secondary text-sm" :disabled="busy" @click="saveQuiet">Saqlash</button>
      <p class="text-xs text-slate-400 flex-1 min-w-48">Shu oraliqda eslatmalar yuborilmaydi, ertalabga qoldiriladi (tasdiqlash kodi bundan mustasno).</p>
    </div>
    <p v-if="error" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <div v-for="t in templates" :key="t.key + t.language" :class="['border rounded-xl p-3 space-y-2', dark ? 'border-slate-800' : 'border-slate-200']">
      <div class="flex items-center gap-2 text-sm">
        <span class="font-medium" :class="dark ? 'text-slate-200' : 'text-slate-800'">{{ labels[t.key] || t.key }}</span>
        <span class="badge-blue">{{ t.language === 'uz' ? "O'zbekcha" : 'Русский' }}</span>
        <span v-if="t.is_default" class="text-xs text-slate-400">standart</span>
        <span class="flex-1"></span>
        <button v-if="!t.is_default" class="text-xs text-slate-500 underline" @click="reset(t)">Standartga qaytarish</button>
      </div>
      <textarea v-model="drafts[t.key + t.language]" rows="2" class="input text-sm" />
      <div class="flex items-center gap-2 text-xs text-slate-400">
        <span class="flex-1">{{ t.placeholders.map(p => '{' + p + '}').join(' ') }} · {{ (drafts[t.key + t.language] || '').length }} belgi</span>
        <button class="btn-secondary text-xs" :disabled="busy || drafts[t.key + t.language] === t.body" @click="save(t)">Saqlash</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'

const toast = useToast(), theme = useThemeStore()
const dark = computed(() => theme.isDark)
const labels = { reminder_24h: '24 soat oldin eslatma', reminder_2h: '2 soat oldin eslatma', otp: 'Tasdiqlash kodi (OTP)', booking_confirmation: 'Yozilish tasdig\'i', waitlist_offer: 'Bo\'sh vaqt taklifi', recall: 'Qayta tashrif eslatmasi' }
const templates = ref([]), drafts = reactive({}), error = ref(false), busy = ref(false)
const quiet = reactive({ quiet_start_hour: 21, quiet_end_hour: 8 })

async function load() {
  error.value = false
  try {
    templates.value = (await api.get('/message-templates')).data
    templates.value.forEach(t => { drafts[t.key + t.language] = t.body })
    Object.assign(quiet, (await api.get('/settings/messaging')).data)
  } catch (e) { error.value = true; toast.error(e, "Xabar sozlamalarini yuklab bo'lmadi") }
}
async function save(t) {
  busy.value = true
  try { await api.put(`/message-templates/${t.key}/${t.language}`, { body: drafts[t.key + t.language] }); toast.success('Shablon saqlandi'); await load() } catch (e) { toast.error(e, "Saqlab bo'lmadi") } finally { busy.value = false }
}
async function reset(t) { try { await api.delete(`/message-templates/${t.key}/${t.language}`); toast.success('Standart tiklandi'); await load() } catch (e) { toast.error(e, "Tiklab bo'lmadi") } }
async function saveQuiet() {
  busy.value = true
  try { Object.assign(quiet, (await api.put('/settings/messaging', { ...quiet })).data); toast.success('Saqlandi') } catch (e) { toast.error(e, "Saqlab bo'lmadi") } finally { busy.value = false }
}
onMounted(load)
</script>
