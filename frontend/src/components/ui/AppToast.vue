<template>
  <div class="fixed top-4 right-4 z-[100] flex flex-col gap-2 w-80 max-w-[calc(100vw-2rem)]" aria-live="polite">
    <TransitionGroup name="toast">
      <div
        v-for="t in toasts"
        :key="t.id"
        role="status"
        :class="['flex items-start gap-2 rounded-xl px-4 py-3 text-sm shadow-lg border cursor-pointer', styles[t.type]]"
        @click="dismiss(t.id)"
      >
        <span class="flex-1 break-words">{{ t.message }}</span>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { toasts, dismiss } from '@/composables/useToast'

const styles = {
  success: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  error: 'bg-red-50 text-red-800 border-red-200',
  info: 'bg-slate-50 text-slate-800 border-slate-200',
}
</script>

<style scoped>
.toast-enter-active, .toast-leave-active { transition: all .2s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(12px); }
</style>
