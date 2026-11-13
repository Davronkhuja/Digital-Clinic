<template>
  <div class="min-h-screen flex items-center justify-center p-4 bg-slate-50">
    <div class="w-full max-w-md bg-white rounded-2xl shadow-lg p-6 space-y-4">
      <p v-if="loading" class="text-center text-slate-400 text-sm">Yuklanmoqda...</p>
      <div v-else-if="gone" class="text-center space-y-2"><h1 class="text-lg font-semibold text-slate-900">Taklif yaroqsiz</h1><p class="text-sm text-slate-500">Havola muddati tugagan. Iltimos, klinikaga qo'ng'iroq qiling.</p></div>
      <template v-else-if="done">
        <h1 class="text-lg font-semibold text-emerald-700">Siz yozildingiz</h1>
        <p class="text-sm text-slate-600">{{ done.date }} {{ done.time }}, {{ done.doctor }}</p>
      </template>
      <template v-else-if="info">
        <h1 class="text-lg font-semibold text-slate-900">{{ info.clinic }}: bo'sh vaqt</h1>
        <div class="rounded-xl bg-slate-50 p-4 text-sm space-y-1"><p><span class="text-slate-400">Sana:</span> <b>{{ info.date }}</b></p><p><span class="text-slate-400">Vaqt:</span> <b>{{ info.time }}</b></p><p><span class="text-slate-400">Shifokor:</span> <b>{{ info.doctor }}</b></p></div>
        <button v-if="info.available" class="w-full px-4 py-2.5 rounded-xl bg-cyan-600 text-white text-sm font-medium disabled:opacity-60" :disabled="busy" @click="book">Shu vaqtga yozilaman</button>
        <p v-else class="text-sm text-amber-600">Bu taklif endi mavjud emas.</p>
        <p v-if="message" class="text-sm text-red-600">{{ message }}</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/composables/useApi'

const route = useRoute()
const info = ref(null), done = ref(null), loading = ref(true), gone = ref(false), busy = ref(false), message = ref('')
onMounted(async () => {
  try { info.value = (await api.get(`/public/offers/${route.params.token}`)).data } catch { gone.value = true } finally { loading.value = false }
})
async function book() {
  busy.value = true
  try { done.value = (await api.post(`/public/offers/${route.params.token}/book`)).data } catch (e) { message.value = e?.response?.data?.detail || "Yozib bo'lmadi" } finally { busy.value = false }
}
</script>
