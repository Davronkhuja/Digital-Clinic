<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
    <div class="relative w-full max-w-md">
      <div class="bg-white/5 backdrop-blur-xl border border-white/10 rounded-3xl p-8 shadow-2xl">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 shadow-lg mb-4">
            <KeyRound class="w-7 h-7 text-white" />
          </div>
          <h1 class="font-heading text-2xl font-bold text-white">Parolni tiklash</h1>
          <p class="text-slate-400 text-sm mt-1">Email orqali avtomatik tiklash hozircha mavjud emas</p>
        </div>
        <p class="text-amber-300 text-sm text-center bg-amber-500/10 rounded-lg py-3 px-4">
          Parolni tiklash uchun administratorga murojaat qiling.
        </p>
        <p class="text-center text-slate-500 text-sm mt-6">
          <RouterLink to="/login" class="text-cyan-400 hover:text-cyan-300">← Kirishga qaytish</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
import { KeyRound } from 'lucide-vue-next'
</script>
