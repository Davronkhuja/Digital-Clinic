<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center p-4">
    <div class="text-center">
      <p class="text-8xl font-heading font-bold gradient-text">404</p>
      <h1 class="text-2xl font-heading font-bold text-slate-900 mt-4">Sahifa topilmadi</h1>
      <p class="text-slate-500 mt-2">Kechirasiz, bu sahifa mavjud emas.</p>
      <RouterLink to="/" class="btn-primary mt-6 inline-flex">
        Bosh sahifaga qaytish
      </RouterLink>
    </div>
  </div>
</template>

<script setup>
import { RouterLink } from 'vue-router'
</script>
