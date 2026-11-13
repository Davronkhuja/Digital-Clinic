<template>
  <div :class="['rounded-2xl border p-4 space-y-3', dark ? 'border-slate-800 bg-slate-800/20' : 'border-slate-200']">
    <h4 :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">Xabarlarga rozilik</h4>
    <p class="text-xs text-slate-400">Rozilik bo'lmasa eslatma va boshqa xabarlar yuborilmaydi. Voz kechish istalgan vaqtda mumkin.</p>
    <p v-if="error" class="text-xs text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <template v-else-if="prefs">
      <div v-for="c in prefs.consents" :key="c.channel" class="flex items-center gap-3 text-sm">
        <label class="flex items-center gap-2 flex-1" :class="canEdit ? 'cursor-pointer' : ''">
          <input type="checkbox" :checked="c.status === 'Granted'" :disabled="!canEdit || busy" @change="toggle(c, $event.target.checked)" />
          {{ c.channel === 'SMS' ? 'SMS' : 'Telegram' }}
          <span v-if="c.channel === 'Telegram'" class="text-xs" :class="prefs.telegram_linked ? 'text-emerald-600' : 'text-slate-400'">{{ prefs.telegram_linked ? "(ulangan)" : "(bot ulanmagan)" }}</span>
        </label>
        <span v-if="c.status === 'Granted' && c.granted_at" class="text-xs text-slate-400">{{ c.granted_at.slice(0, 10) }} · {{ c.source }}</span>
        <span v-else-if="c.revoked_at" class="text-xs text-slate-400">voz kechgan {{ c.revoked_at.slice(0, 10) }}</span>
      </div>
      <div class="flex items-center gap-2 text-sm">
        <span class="text-xs text-slate-400">Xabarlar tili</span>
        <select class="input w-auto py-1 text-sm" :value="prefs.language" :disabled="!canEdit || busy" @change="setLanguage($event.target.value)">
          <option value="uz">O'zbekcha (lotin)</option><option value="ru">Русский</option>
        </select>
      </div>
      <input v-if="canEdit" v-model="note" class="input text-xs" placeholder="Izoh (masalan: qog'oz rozilik shakli raqami)" maxlength="300" />
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({ patientId: { type: String, required: true } })
const toast = useToast(), theme = useThemeStore(), auth = useAuthStore()
const dark = computed(() => theme.isDark)
const canEdit = computed(() => auth.can('patients:write'))
const prefs = ref(null), error = ref(false), busy = ref(false), note = ref('')

async function load() {
  error.value = false
  try { prefs.value = (await api.get(`/patients/${props.patientId}/contact-preferences`)).data } catch (e) { error.value = true; toast.error(e, "Rozilikni yuklab bo'lmadi") }
}
async function toggle(c, granted) {
  busy.value = true
  try { prefs.value = (await api.put(`/patients/${props.patientId}/consents`, { channel: c.channel, granted, note: note.value || null })).data; toast.success(granted ? 'Rozilik qayd etildi' : 'Voz kechish qayd etildi') }
  catch (e) { toast.error(e, "Saqlab bo'lmadi"); await load() } finally { busy.value = false }
}
async function setLanguage(language) {
  busy.value = true
  try { prefs.value = (await api.put(`/patients/${props.patientId}/language`, { language })).data } catch (e) { toast.error(e, "Saqlab bo'lmadi"); await load() } finally { busy.value = false }
}
onMounted(load)
</script>
