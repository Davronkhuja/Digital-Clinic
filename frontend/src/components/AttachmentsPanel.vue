<template>
  <div :class="['rounded-2xl border p-4 space-y-3', dark ? 'border-slate-800 bg-slate-800/20' : 'border-slate-200']">
    <div class="flex items-center justify-between gap-2">
      <h4 :class="['font-semibold text-sm flex items-center gap-2', dark ? 'text-white' : 'text-slate-900']"><Paperclip class="w-4 h-4 text-cyan-500" /> {{ title }}</h4>
      <label v-if="auth.can('emr:write')" :class="['btn-secondary text-xs cursor-pointer', uploading ? 'opacity-60 pointer-events-none' : '']">
        <Upload class="w-3.5 h-3.5" /> {{ uploading ? 'Yuklanmoqda...' : 'Fayl biriktirish' }}
        <input type="file" class="hidden" accept=".pdf,.jpg,.jpeg,.png,.dcm,application/pdf,image/jpeg,image/png,application/dicom" multiple @change="onPick" />
      </label>
    </div>
    <p class="text-xs text-slate-400">PDF, JPG, PNG, DICOM · bittasi {{ maxMb }} MB gacha</p>
    <p v-if="loading" class="text-xs text-slate-400">Yuklanmoqda...</p>
    <p v-else-if="error" class="text-xs text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <p v-else-if="!items.length" class="text-xs text-slate-400">Fayl biriktirilmagan</p>
    <ul v-else class="space-y-1.5">
      <li v-for="a in items" :key="a.id" class="flex items-center gap-2 text-sm">
        <span class="badge-slate text-[10px] uppercase">{{ ext(a) }}</span>
        <button class="flex-1 text-left truncate hover:text-cyan-600" :class="dark ? 'text-slate-200' : 'text-slate-700'" :title="a.note || a.filename" @click="download(a)">{{ a.filename }}</button>
        <span class="text-xs text-slate-400 whitespace-nowrap">{{ size(a.size_bytes) }} · {{ a.created_at.slice(0, 10) }}</span>
        <button v-if="auth.can('emr:write')" class="text-slate-400 hover:text-red-500" title="Olib tashlash" @click="remove(a)"><Trash2 class="w-3.5 h-3.5" /></button>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Paperclip, Upload, Trash2 } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'

const props = defineProps({
  patientId: { type: String, required: true },
  encounterId: { type: String, default: '' },
  title: { type: String, default: 'Ilovalar' },
})
const toast = useToast()
const theme = useThemeStore()
const auth = useAuthStore()
const dark = computed(() => theme.isDark)
const maxMb = 20

const items = ref([]), loading = ref(true), error = ref(false), uploading = ref(false)
const ext = a => ({ 'application/pdf': 'pdf', 'image/jpeg': 'jpg', 'image/png': 'png', 'application/dicom': 'dcm' }[a.content_type] || '?')
const size = b => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`)

async function load() {
  loading.value = true
  error.value = false
  try {
    const params = props.encounterId ? { encounter_id: props.encounterId } : {}
    items.value = (await api.get(`/patients/${props.patientId}/attachments`, { params })).data
  } catch (e) {
    items.value = []
    error.value = true
    toast.error(e, "Ilovalarni yuklab bo'lmadi")
  } finally { loading.value = false }
}

async function onPick(e) {
  const files = Array.from(e.target.files)
  e.target.value = ''
  uploading.value = true
  for (const file of files) {
    if (file.size > maxMb * 1048576) { toast.error(`${file.name}: ${maxMb} MB dan katta`); continue }
    const body = new FormData()
    body.append('file', file)
    if (props.encounterId) body.append('encounter_id', props.encounterId)
    try {
      await api.post(`/patients/${props.patientId}/attachments`, body, { headers: { 'Content-Type': 'multipart/form-data' } })
      toast.success(`${file.name} biriktirildi`)
    } catch (err) { toast.error(err, `${file.name}: yuklab bo'lmadi`) }
  }
  uploading.value = false
  await load()
}

async function download(a) {
  try {
    const { data } = await api.get(`/attachments/${a.id}/download`, { responseType: 'blob' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(data)
    link.download = a.filename
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (err) { toast.error(err, "Faylni yuklab olib bo'lmadi") }
}

async function remove(a) {
  try {
    await api.delete(`/attachments/${a.id}`)
    toast.success('Fayl olib tashlandi')
    await load()
  } catch (err) { toast.error(err, "Olib tashlab bo'lmadi") }
}

watch(() => [props.patientId, props.encounterId], load)
onMounted(load)
</script>
