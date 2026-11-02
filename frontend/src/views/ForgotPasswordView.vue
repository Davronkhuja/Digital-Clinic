<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
    <div class="relative w-full max-w-md">
      <div class="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg mb-4">
            <KeyRound class="w-7 h-7 text-white" />
          </div>
          <h1 class="font-heading text-2xl font-bold text-white">Parolni tiklash</h1>
          <p class="text-slate-400 text-sm mt-1">Emailingizga tiklash havolasi yuboramiz</p>
        </div>
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="text-sm font-medium text-slate-300 block mb-1.5">Email</label>
            <input v-model="email" type="email" class="w-full px-4 py-3 rounded-xl bg-white/10 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 transition-all" placeholder="email@clinic.uz" required />
          </div>
          <button type="submit" :disabled="loading" class="w-full py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 transition-all disabled:opacity-50">
            {{ loading ? 'Yuborilmoqda...' : 'Tiklash havolasini yuborish' }}
          </button>
          <p v-if="sent" class="text-emerald-400 text-sm text-center bg-emerald-500/10 rounded-lg py-2">Havola yuborildi! Emailingizni tekshiring.</p>
        </form>
        <p class="text-center text-slate-500 text-sm mt-6">
          <RouterLink to="/login" class="text-cyan-400 hover:text-cyan-300">← Kirishga qaytish</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { KeyRound } from 'lucide-vue-next'
import api from '@/composables/useApi'

const email = ref('')
const loading = ref(false)
const sent = ref(false)

async function handleSubmit() {
  loading.value = true
  try {
    await api.post('/auth/forgot-password', { email: email.value })
    sent.value = true
  } finally {
    loading.value = false
  }
}
</script>
