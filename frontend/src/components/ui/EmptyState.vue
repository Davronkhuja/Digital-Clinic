<template>
  <div class="flex flex-col items-center justify-center text-center py-12 px-4">
    <p class="font-semibold text-slate-700 dark:text-slate-200">{{ title }}</p>
    <p v-if="description" class="text-sm mt-1 text-slate-500 dark:text-slate-400 max-w-sm">{{ description }}</p>
    <button v-if="actionLabel" class="btn-primary text-sm mt-4" @click="$emit('action')">{{ actionLabel }}</button>
    <slot />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  actionLabel: { type: String, default: '' },
})
defineEmits(['action'])
</script>
