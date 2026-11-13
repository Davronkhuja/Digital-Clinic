<template>
  <div v-if="branches.length > 1" class="flex items-center gap-1.5" data-testid="branch-switcher">
    <Building2 class="w-4 h-4 text-slate-400" />
    <select :value="current" :class="['rounded-xl text-sm py-1.5 pl-2 pr-6 border font-medium', dark ? 'bg-slate-800 border-slate-700 text-slate-200' : 'bg-white border-slate-200 text-slate-700']"
      aria-label="Faol filial" data-testid="branch-select" @change="switchBranch">
      <option v-for="b in branches" :key="b.id" :value="b.id">{{ b.name }}</option>
    </select>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Building2 } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

// Faqat `branches:all` ruxsati bor foydalanuvchi (administrator) va filial bittadan ko'p bo'lsa ko'rinadi.
const auth = useAuthStore(), theme = useThemeStore()
const dark = computed(() => theme.isDark)
const branches = ref([])
const current = computed(() => branches.value.find(b => b.current)?.id)

function switchBranch(ev) {
  localStorage.setItem('branch_id', ev.target.value)
  window.location.reload()            // hamma ro'yxat yangi filial bo'yicha qayta yuklansin
}

onMounted(async () => {
  if (!auth.can('branches:all')) return
  try { branches.value = (await api.get('/branches')).data } catch { branches.value = [] }
})
</script>
