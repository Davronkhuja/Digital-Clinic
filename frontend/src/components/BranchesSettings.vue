<template>
  <div class="card p-5 space-y-4 max-w-4xl">
    <div class="flex items-center justify-between gap-3 flex-wrap">
      <div>
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Filiallar</h3>
        <p class="text-xs text-slate-400 mt-0.5">Bemorlar bazasi umumiy. Jadval, kassa, ombor va hisobotlar filial bo'yicha; xodim bitta filialga biriktiriladi.</p>
      </div>
      <button class="btn-primary text-sm" data-testid="branch-new" @click="openNew"><Plus class="w-4 h-4" /> Yangi filial</button>
    </div>
    <p v-if="error" class="text-sm text-red-500">Yuklab bo'lmadi. <button class="underline" @click="load">Qayta urinish</button></p>
    <EmptyState v-else-if="!rows.length" title="Filial yo'q" />
    <div v-else class="table-container rounded-none border-0">
      <table class="table" data-testid="branch-table">
        <thead><tr><th>Nomi</th><th>Manzil</th><th>Telefon</th><th class="text-right">Xodimlar</th><th>Holat</th><th></th></tr></thead>
        <tbody>
          <tr v-for="b in rows" :key="b.id" :class="b.is_active ? '' : 'opacity-60'">
            <td class="font-medium">{{ b.name }} <span v-if="b.is_default" class="badge-blue ml-1">Asosiy</span><span v-if="b.current" class="badge-green ml-1">Faol</span></td>
            <td class="text-sm text-slate-500">{{ b.address || '—' }}</td><td class="text-sm text-slate-500">{{ b.phone || '—' }}</td>
            <td class="text-right font-mono">{{ b.users_count }}</td>
            <td><span :class="b.is_active ? 'badge-green' : 'badge-slate'">{{ b.is_active ? 'Faol' : 'Nofaol' }}</span></td>
            <td class="whitespace-nowrap"><button class="text-xs text-cyan-600 hover:underline mr-3" @click="openEdit(b)">Tahrirlash</button>
              <button v-if="!b.is_default && !b.current" class="text-xs hover:underline" :class="b.is_active ? 'text-red-500' : 'text-emerald-600'" @click="toggle(b)">{{ b.is_active ? 'Faolsizlantirish' : 'Faollashtirish' }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showForm" class="modal-overlay" @click.self="showForm = false">
      <div :class="['w-full max-w-md rounded-2xl shadow-2xl p-6 space-y-3', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ form.id ? 'Filialni tahrirlash' : 'Yangi filial' }}</h3>
        <div><label class="text-xs text-slate-400 block mb-1">Nomi *</label><input v-model="form.name" class="input" maxlength="200" data-testid="branch-name" /></div>
        <div><label class="text-xs text-slate-400 block mb-1">Manzil</label><input v-model="form.address" class="input" maxlength="300" /></div>
        <div><label class="text-xs text-slate-400 block mb-1">Telefon</label><input v-model="form.phone" class="input" maxlength="40" /></div>
        <p v-if="!form.id" class="text-xs text-slate-400">Klinika sozlamalari (nom, valyuta, til, chegirma limiti ...) asosiy filialdan nusxalanadi.</p>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="showForm = false">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="branch-save" @click="save">Saqlash</button></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast(), theme = useThemeStore()
const dark = computed(() => theme.isDark)
const rows = ref([]), error = ref(false), busy = ref(false), showForm = ref(false)
const form = reactive({ id: null, name: '', address: '', phone: '' })

async function load() {
  error.value = false
  try { rows.value = (await api.get('/branches', { params: { include_inactive: true } })).data } catch (e) { error.value = true; toast.error(e, "Filiallarni yuklab bo'lmadi") }
}
function openNew() { Object.assign(form, { id: null, name: '', address: '', phone: '' }); showForm.value = true }
function openEdit(b) { Object.assign(form, { id: b.id, name: b.name, address: b.address || '', phone: b.phone || '' }); showForm.value = true }
async function save() {
  busy.value = true
  const body = { name: form.name.trim(), address: form.address.trim() || null, phone: form.phone.trim() || null }
  try {
    if (form.id) await api.put(`/branches/${form.id}`, body)
    else await api.post('/branches', body)
    toast.success('Filial saqlandi'); showForm.value = false; await load()
  } catch (e) { toast.error(e, "Filialni saqlab bo'lmadi") } finally { busy.value = false }
}
async function toggle(b) {
  try { await api.put(`/branches/${b.id}`, { is_active: !b.is_active }); toast.success(b.is_active ? 'Filial faolsizlantirildi' : 'Filial faollashtirildi'); await load() }
  catch (e) { toast.error(e, "Holatni o'zgartirib bo'lmadi") }
}
onMounted(load)
</script>
