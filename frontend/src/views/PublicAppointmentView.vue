<template>
  <div class="min-h-screen flex items-center justify-center p-4 bg-slate-50">
    <div class="w-full max-w-md bg-white rounded-2xl shadow-lg p-6 space-y-4">
      <p v-if="loading" class="text-center text-slate-400 text-sm">Yuklanmoqda...</p>
      <div v-else-if="gone" class="text-center space-y-2"><h1 class="text-lg font-semibold text-slate-900">Havola yaroqsiz</h1><p class="text-sm text-slate-500">Havola muddati tugagan yoki noto'g'ri. Iltimos, klinikaga qo'ng'iroq qiling.</p></div>
      <template v-else-if="info">
        <h1 class="text-lg font-semibold text-slate-900">{{ info.clinic }}</h1>
        <div class="rounded-xl bg-slate-50 p-4 text-sm space-y-1">
          <p><span class="text-slate-400">Sana:</span> <b>{{ info.date }}</b></p><p><span class="text-slate-400">Vaqt:</span> <b>{{ info.time }}</b></p><p><span class="text-slate-400">Shifokor:</span> <b>{{ info.doctor }}</b></p>
        </div>
        <p v-if="info.status === 'Cancelled'" class="text-sm text-red-600">Qabul bekor qilingan.</p>
        <p v-else-if="info.confirmed" class="text-sm text-emerald-600">Qabul tasdiqlangan. Kutib qolamiz!</p>
        <div v-if="info.can_act" class="flex gap-3">
          <button class="flex-1 px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-medium disabled:opacity-60" :disabled="busy || info.confirmed" @click="act('confirm')">Tasdiqlayman</button>
          <button class="flex-1 px-4 py-2.5 rounded-xl border border-red-300 text-red-600 text-sm font-medium disabled:opacity-60" :disabled="busy" @click="act('cancel')">Bekor qilaman</button>
        </div>
        <p v-if="message" class="text-sm text-slate-600">{{ message }}</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/composables/useApi'

const route = useRoute()
const info = ref(null), loading = ref(true), gone = ref(false), busy = ref(false), message = ref('')
const base = () => `/public/appointments/${route.params.token}`
onMounted(async () => {
  try { info.value = (await api.get(base())).data } catch { gone.value = true } finally { loading.value = false }
})
async function act(kind) {
  if (kind === 'cancel' && !window.confirm('Qabulni bekor qilasizmi?')) return
  busy.value = true
  try { info.value = (await api.post(`${base()}/${kind}`)).data; message.value = kind === 'confirm' ? 'Rahmat, qabul tasdiqlandi.' : 'Qabul bekor qilindi.' }
  catch (e) { message.value = e?.response?.data?.detail || "Amalni bajarib bo'lmadi" } finally { busy.value = false }
}
</script>
