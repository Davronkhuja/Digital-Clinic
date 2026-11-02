<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
    <div class="absolute inset-0 overflow-hidden">
      <div class="absolute -top-1/2 -right-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl"></div>
      <div class="absolute -bottom-1/4 -left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl"></div>
    </div>
    <div class="relative w-full max-w-md">
      <div class="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg mb-4">
            <span class="font-heading text-xl font-bold text-white">DC</span>
          </div>
          <h1 class="font-heading text-2xl font-bold text-white">Ro'yxatdan o'tish</h1>
          <p class="text-slate-400 text-sm mt-1">Yangi klinika hisob yarating</p>
        </div>

        <form @submit.prevent="handleRegister" class="space-y-4">
          <div>
            <label class="text-sm font-medium text-slate-300 block mb-1.5">To'liq ism</label>
            <input v-model="form.name" type="text" class="w-full px-4 py-3 rounded-xl bg-white/10 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 transition-all" placeholder="Ahmad Karimov" required />
          </div>
          <div>
            <label class="text-sm font-medium text-slate-300 block mb-1.5">Email</label>
            <input v-model="form.email" type="email" class="w-full px-4 py-3 rounded-xl bg-white/10 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 transition-all" placeholder="ahmad@clinic.uz" required />
          </div>
          <div>
            <label class="text-sm font-medium text-slate-300 block mb-1.5">Klinika nomi</label>
            <input v-model="form.clinic_name" type="text" class="w-full px-4 py-3 rounded-xl bg-white/10 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 transition-all" placeholder="Hayot Klinikasi" required />
          </div>
          <div>
            <label class="text-sm font-medium text-slate-300 block mb-1.5">Parol</label>
            <input v-model="form.password" type="password" class="w-full px-4 py-3 rounded-xl bg-white/10 border border-white/10 text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 transition-all" placeholder="••••••••" required />
          </div>
          <button type="submit" :disabled="loading" class="w-full py-3 rounded-xl font-semibold text-white bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 transition-all disabled:opacity-50">
            {{ loading ? 'Yuborilmoqda...' : "Ro'yxatdan o'tish" }}
          </button>
          <p v-if="error" class="text-red-400 text-sm text-center">{{ error }}</p>
          <p v-if="success" class="text-emerald-400 text-sm text-center">{{ success }}</p>
        </form>
        <p class="text-center text-slate-500 text-sm mt-6">
          Hisob bor?
          <RouterLink to="/login" class="text-cyan-400 hover:text-cyan-300 font-medium">Kirish</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const loading = ref(false)
const error = ref('')
const success = ref('')
const form = reactive({ name: '', email: '', password: '', clinic_name: '' })

async function handleRegister() {
  loading.value = true
  error.value = ''
  try {
    await auth.register(form)
    success.value = "Muvaffaqiyatli ro'yxatdan o'tdingiz! Kirish sahifasiga yo'naltirilmoqda..."
    setTimeout(() => router.push('/login'), 2000)
  } catch (err) {
    error.value = err.response?.data?.detail || 'Xato yuz berdi'
  } finally {
    loading.value = false
  }
}
</script>
