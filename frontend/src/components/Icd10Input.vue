<template>
  <div class="relative">
    <input v-model="text" class="input" :placeholder="placeholder" autocomplete="off" @input="onInput" @focus="search" @blur="close" />
    <ul v-if="open && results.length" class="absolute z-30 left-0 right-0 mt-1 max-h-56 overflow-y-auto rounded-xl border bg-white dark:bg-slate-800 dark:border-slate-700 shadow-xl text-sm">
      <li v-for="c in results" :key="c.code">
        <button type="button" class="w-full text-left px-3 py-2 hover:bg-cyan-50 dark:hover:bg-slate-700" @mousedown.prevent="pick(c)">
          <span class="font-mono font-semibold text-cyan-600">{{ c.code }}</span>
          <span class="ml-2 text-slate-600 dark:text-slate-300">{{ c.name_uz }}</span>
        </button>
      </li>
    </ul>
    <p v-else-if="open && text && !loading" class="absolute z-30 left-0 mt-1 text-xs text-amber-600">MKB-10 da topilmadi</p>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '@/composables/useApi'

const props = defineProps({ modelValue: { type: String, default: '' }, placeholder: { type: String, default: 'MKB-10: kod yoki nom (masalan J06)' } })
const emit = defineEmits(['update:modelValue', 'pick'])

const text = ref(props.modelValue)
const results = ref([]), open = ref(false), loading = ref(false)
let timer
watch(() => props.modelValue, v => { if (v !== text.value) text.value = v })

function onInput() {
  emit('update:modelValue', text.value.trim().toUpperCase())
  clearTimeout(timer)
  timer = setTimeout(search, 250)
}
async function search() {
  open.value = true
  loading.value = true
  try {
    results.value = (await api.get('/icd10', { params: { search: text.value, limit: 12 } })).data
  } catch {
    results.value = [] // ma'lumotnoma yuklanmasa, kod qo'lda kiritiladi (server tekshiradi)
  } finally { loading.value = false }
}
function pick(c) {
  text.value = c.code
  emit('update:modelValue', c.code)
  emit('pick', c)
  open.value = false
}
function close() { setTimeout(() => { open.value = false }, 100) }
</script>
