<template>
  <div class="card p-5 space-y-4 max-w-3xl">
    <div class="flex items-center justify-between gap-3">
      <div>
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Ko'rik shablonlari</h3>
        <p class="text-xs text-slate-400 mt-0.5">Shikoyat, anamnez, ko'rik va tavsiya uchun boshlang'ich matn. Ko'rik yozishda tanlanadi; yozilgan ko'riklarga ta'sir qilmaydi.</p>
      </div>
      <button class="btn-primary text-sm" @click="openNew"><Plus class="w-4 h-4" /> Yangi shablon</button>
    </div>

    <p v-if="error" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <EmptyState v-else-if="!items.length" title="Shablon yo'q" description="Birinchi shablonni qo'shing" />
    <ul v-else class="divide-y" :class="dark ? 'divide-slate-800' : 'divide-slate-100'">
      <li v-for="t in items" :key="t.id" class="py-2.5 flex items-center gap-3 text-sm">
        <span :class="['flex-1 font-medium', t.is_active ? '' : 'line-through text-slate-400', dark ? 'text-slate-200' : 'text-slate-800']">{{ t.name }}</span>
        <span v-if="t.specialty" class="text-xs text-slate-400">{{ t.specialty }}</span>
        <span :class="t.is_active ? 'badge-green' : 'badge-slate'">{{ t.is_active ? 'Faol' : 'Nofaol' }}</span>
        <button class="text-slate-400 hover:text-cyan-600" title="Tahrirlash" @click="openEdit(t)"><Pencil class="w-4 h-4" /></button>
        <button class="text-red-500" title="O'chirish" @click="remove(t)"><Trash2 class="w-4 h-4" /></button>
      </li>
    </ul>

    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div :class="['w-full max-w-xl rounded-2xl shadow-2xl p-6 max-h-[92vh] overflow-y-auto space-y-3', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ editingId ? 'Shablonni tahrirlash' : 'Yangi shablon' }}</h3>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="text-xs text-slate-400 block mb-1">Nomi *</label><input v-model="form.name" class="input" maxlength="120" /></div>
          <div><label class="text-xs text-slate-400 block mb-1">Mutaxassislik</label><input v-model="form.specialty" class="input" maxlength="100" /></div>
        </div>
        <div v-for="f in fields" :key="f.key"><label class="text-xs text-slate-400 block mb-1">{{ f.label }}</label><textarea v-model="form[f.key]" rows="3" class="input" /></div>
        <label class="flex items-center gap-2 text-sm"><input v-model="form.is_active" type="checkbox" /> Faol</label>
        <div class="flex justify-end gap-2 pt-2">
          <button class="btn-secondary" @click="showForm = false">Bekor qilish</button>
          <button class="btn-primary" :disabled="saving || form.name.trim().length < 2" @click="save">Saqlash</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Pencil, Trash2 } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast()
const theme = useThemeStore()
const dark = computed(() => theme.isDark)
const fields = [
  { key: 'complaints', label: 'Shikoyatlar' }, { key: 'anamnesis', label: 'Anamnez' }, { key: 'examination', label: "Ob'ektiv ko'rik" },
  { key: 'diagnosis', label: 'Tashxis (ixtiyoriy)' }, { key: 'recommendations', label: 'Tavsiyalar' },
]
const blank = () => ({ name: '', specialty: '', complaints: '', anamnesis: '', examination: '', diagnosis: '', recommendations: '', is_active: true })

const items = ref([]), error = ref(false), saving = ref(false), showForm = ref(false), editingId = ref(null)
const form = reactive(blank())

async function load() {
  error.value = false
  try { items.value = (await api.get('/emr-templates', { params: { include_inactive: true } })).data } catch (e) {
    items.value = []; error.value = true; toast.error(e, "Shablonlarni yuklab bo'lmadi")
  }
}
function openNew() { editingId.value = null; Object.assign(form, blank()); showForm.value = true }
function openEdit(t) { editingId.value = t.id; Object.assign(form, blank(), t); showForm.value = true }
async function save() {
  saving.value = true
  const body = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, typeof v === 'string' ? (v.trim() || null) : v]))
  body.name = form.name.trim()
  try {
    if (editingId.value) await api.put(`/emr-templates/${editingId.value}`, body)
    else await api.post('/emr-templates', body)
    toast.success('Shablon saqlandi')
    showForm.value = false
    await load()
  } catch (e) { toast.error(e, "Shablonni saqlab bo'lmadi") } finally { saving.value = false }
}
async function remove(t) {
  try { await api.delete(`/emr-templates/${t.id}`); toast.success("Shablon o'chirildi"); await load() } catch (e) { toast.error(e, "Shablonni o'chirib bo'lmadi") }
}
onMounted(load)
</script>
