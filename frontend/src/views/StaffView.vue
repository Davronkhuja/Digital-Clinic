<template>
  <div class="space-y-5 animate-fade-in">

    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Staff Management</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Manage your team and permissions</p>
      </div>
      <button class="btn-primary flex-shrink-0" @click="openAdd"><Plus class="w-4 h-4" /> Add Staff</button>
    </div>

    <!-- Staff List -->
    <div class="card">

      <!-- Search -->
      <div :class="['p-4 border-b', dark ? 'border-slate-800' : 'border-slate-100']">
        <div class="relative max-w-sm">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input v-model="search" class="input pl-9" placeholder="Search staff..." />
        </div>
      </div>

      <!-- Table -->
      <div v-if="loading" class="p-12 text-center">
        <div class="animate-spin w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto mb-3"></div>
        <p class="text-slate-400 text-sm">Yuklanmoqda...</p>
      </div>

      <EmptyState v-else-if="loadError" title="Xodimlarni yuklab bo'lmadi" description="Server bilan aloqa o'rnatilmadi. Qayta urinib ko'ring." action-label="Qayta urinish" @action="fetchStaff" />

      <EmptyState v-else-if="staff.length === 0" title="Hali xodimlar yo'q" description="Birinchi xodimni qo'shing" action-label="Add Staff" @action="openAdd" />

      <div v-else class="overflow-x-auto">
        <table class="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Role</th>
              <th>Department</th>
              <th>Status</th>
              <th>Patients</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in filtered" :key="s.id" :class="dark ? 'hover:bg-slate-800/40' : 'hover:bg-slate-50'">
              <td>
                <div class="flex items-center gap-3">
                  <div class="w-8 h-8 rounded-full overflow-hidden flex-shrink-0">
                    <img v-if="s.avatar" :src="s.avatar" class="w-full h-full object-cover" />
                    <div v-else :class="['w-full h-full flex items-center justify-center text-xs font-bold text-white', avatarBg(s.name)]">
                      {{ initials(s.name) }}
                    </div>
                  </div>
                  <span :class="['font-medium', dark ? 'text-slate-200' : 'text-slate-900']">{{ s.name }}</span>
                </div>
              </td>
              <td>
                <span :class="['badge text-xs', roleCls(s.role)]">{{ s.role }}</span>
              </td>
              <td :class="dark ? 'text-slate-400' : 'text-slate-600'">{{ s.department || '—' }}</td>
              <td>
                <span :class="s.status === 'Active' ? 'badge-green' : 'badge-slate'">{{ s.status }}</span>
              </td>
              <td :class="['text-sm', dark ? 'text-slate-500' : 'text-slate-400']">{{ s.patients_count ?? '—' }}</td>
              <td>
                <div class="relative" :ref="el => menuRefs[s.id] = el">
                  <button @click.stop="toggleMenu(s.id)"
                    :class="['p-1.5 rounded-lg transition-colors', dark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-100']">
                    <MoreHorizontal class="w-4 h-4" />
                  </button>
                  <Transition name="dropdown">
                    <div v-if="openMenu === s.id"
                      :class="['absolute right-0 top-8 w-36 rounded-xl shadow-xl border z-20 overflow-hidden py-1',
                        dark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200']">
                      <button @click="openEdit(s); openMenu = null" :class="['flex items-center gap-2 w-full px-3 py-2 text-sm', dark ? 'text-slate-300 hover:bg-slate-700' : 'text-slate-700 hover:bg-slate-50']">
                        <Pencil class="w-3.5 h-3.5" /> Edit
                      </button>
                      <button @click="deleteStaff(s.id); openMenu = null" class="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20">
                        <Trash2 class="w-3.5 h-3.5" /> Delete
                      </button>
                    </div>
                  </Transition>
                </div>
              </td>
            </tr>
            <tr v-if="filtered.length === 0">
              <td colspan="6" class="py-12 text-center text-slate-400">Staff not found</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Add/Edit Modal -->
    <Transition name="modal-fade">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div :class="['w-full max-w-xl rounded-2xl shadow-2xl overflow-hidden animate-fade-in max-h-[92vh] flex flex-col', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
          <div :class="['flex items-center justify-between px-6 py-4 border-b flex-shrink-0', dark ? 'border-slate-800' : 'border-slate-200']">
            <h3 :class="['font-heading font-semibold text-lg', dark ? 'text-white' : 'text-slate-900']">
              {{ editingId ? 'Edit Staff' : 'Add Staff' }}
            </h3>
            <button @click="closeModal" :class="['p-1.5 rounded-lg', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><X class="w-4 h-4" /></button>
          </div>

          <div class="overflow-y-auto flex-1 p-6 space-y-5">
            <!-- Avatar -->
            <div class="flex items-center gap-5">
              <div class="relative group cursor-pointer flex-shrink-0" @click="photoInput?.click()">
                <div class="w-20 h-20 rounded-2xl overflow-hidden ring-2 ring-offset-2" :class="dark ? 'ring-slate-700 ring-offset-slate-900' : 'ring-slate-200'">
                  <img v-if="form.avatar" :src="form.avatar" class="w-full h-full object-cover" />
                  <div v-else :class="['w-full h-full flex items-center justify-center text-2xl font-bold text-white', avatarBg(form.name || '?')]">{{ form.name ? initials(form.name) : '?' }}</div>
                </div>
                <div class="absolute inset-0 rounded-2xl bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"><Camera class="w-5 h-5 text-white" /></div>
              </div>
              <input ref="photoInput" type="file" accept="image/*" class="hidden" @change="onPhoto" />
              <div>
                <p :class="['text-sm font-medium mb-2', dark ? 'text-slate-300' : 'text-slate-700']">Profile Photo</p>
                <div class="flex gap-2">
                  <button type="button" class="btn-secondary text-xs !px-3 !py-1.5" @click="photoInput?.click()"><Camera class="w-3.5 h-3.5" />{{ form.avatar ? 'Change' : 'Upload' }}</button>
                  <button v-if="form.avatar" type="button" @click="form.avatar=''" class="p-1.5 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"><Trash2 class="w-3.5 h-3.5" /></button>
                </div>
              </div>
            </div>

            <div :class="['border-t pt-4', dark ? 'border-slate-800' : 'border-slate-100']">
              <div class="grid grid-cols-2 gap-4">
                <div class="col-span-2"><label :class="lbl">Full Name *</label><input v-model="form.name" class="input" placeholder="Dr. Ahmad Karimov" /></div>
                <div><label :class="lbl">Role *</label>
                  <select v-model="form.role" class="input">
                    <option v-for="r in roleOptions" :key="r">{{ r }}</option>
                  </select>
                </div>
                <div><label :class="lbl">Department *</label><input v-model="form.department" class="input" placeholder="Cardiology" /></div>
                <div><label :class="lbl">Phone</label><input v-model="form.phone" class="input" placeholder="+998 90 000 0000" /></div>
                <div><label :class="lbl">Email</label><input v-model="form.email" type="email" class="input" placeholder="email@clinic.uz" /></div>
                <div class="col-span-2"><label :class="lbl">Schedule</label><input v-model="form.schedule" class="input" placeholder="Mon-Fri 09:00-17:00" /></div>
                <div><label :class="lbl">Status</label>
                  <select v-model="form.status" class="input">
                    <option value="Active">Active</option>
                    <option value="Inactive">Inactive</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div :class="['px-6 py-4 border-t flex gap-3 flex-shrink-0', dark ? 'border-slate-800 bg-slate-900/50' : 'border-slate-100 bg-slate-50']">
            <button class="btn-secondary flex-1" @click="closeModal">Cancel</button>
            <button class="btn-primary flex-1" @click="saveStaff" :disabled="saving">
              <Check class="w-4 h-4" />{{ saving ? 'Saving...' : 'Save' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted } from 'vue'
import { Plus, X, Pencil, Trash2, Check, Camera, Search, MoreHorizontal } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/ui/EmptyState.vue'

const theme = useThemeStore()
const dark = computed(() => theme.isDark)
const lbl = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])

const search = ref('')
const openMenu = ref(null)
const menuRefs = ref({})
const showModal = ref(false)
const editingId = ref(null)
const saving = ref(false)
const photoInput = ref(null)
const staff = ref([])
const loading = ref(true)
const loadError = ref(false)

const toast = useToast()
const roleOptions = ['Doctor', 'Nurse', 'Receptionist', 'Admin', 'Cashier', 'Lab Technician']
const defaultForm = () => ({ name: '', role: 'Doctor', department: '', phone: '', email: '', schedule: '', status: 'Active', avatar: '' })
const form = reactive(defaultForm())

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return staff.value
  return staff.value.filter(s => s.name.toLowerCase().includes(q) || s.role.toLowerCase().includes(q) || (s.department || '').toLowerCase().includes(q))
})

function initials(name) {
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()
}

const gradients = ['bg-gradient-to-br from-cyan-500 to-blue-600', 'bg-gradient-to-br from-violet-500 to-purple-600', 'bg-gradient-to-br from-emerald-500 to-teal-600', 'bg-gradient-to-br from-orange-500 to-red-600', 'bg-gradient-to-br from-pink-500 to-rose-600', 'bg-gradient-to-br from-amber-500 to-yellow-500']
function avatarBg(name) { return gradients[(name?.charCodeAt(0) || 0) % gradients.length] }

function roleCls(role) {
  const m = { Doctor: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400', Nurse: 'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-400', Receptionist: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400', Admin: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400', Cashier: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400', 'Lab Technician': 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400' }
  return m[role] || 'bg-slate-100 text-slate-600'
}

function toggleMenu(id) { openMenu.value = openMenu.value === id ? null : id }
function handleOutside(e) { if (!Object.values(menuRefs.value).some(el => el?.contains(e.target))) openMenu.value = null }
onMounted(() => document.addEventListener('mousedown', handleOutside))
onUnmounted(() => document.removeEventListener('mousedown', handleOutside))

function openAdd() { editingId.value = null; Object.assign(form, defaultForm()); showModal.value = true }
function openEdit(s) { editingId.value = s.id; Object.assign(form, { name: s.name, role: s.role, department: s.department, phone: s.phone, email: s.email, schedule: s.schedule || '', status: s.status, avatar: s.avatar || '' }); showModal.value = true }
function closeModal() { showModal.value = false; editingId.value = null }

function onPhoto(e) {
  const file = e.target.files?.[0]; if (!file) return
  const reader = new FileReader()
  reader.onload = ev => { form.avatar = ev.target.result }
  reader.readAsDataURL(file); e.target.value = ''
}

async function saveStaff() {
  saving.value = true
  const payload = { name: form.name, role: form.role, department: form.department, phone: form.phone,
                    email: form.email, schedule: form.schedule || null, status: form.status }
  try {
    if (editingId.value) {
      const { data } = await api.put(`/staff/${editingId.value}`, payload)
      const i = staff.value.findIndex(s => s.id === editingId.value)
      if (i >= 0) staff.value[i] = { ...staff.value[i], ...data, avatar: form.avatar || staff.value[i].avatar }
      toast.success("Xodim ma'lumotlari yangilandi")
    } else {
      const { data } = await api.post('/staff', payload)
      staff.value.push({ ...data, avatar: form.avatar })
      toast.success("Xodim qo'shildi")
    }
    closeModal()
  } catch (e) {
    toast.error(e, "Xodimni saqlab bo'lmadi")
  } finally {
    saving.value = false
  }
}

async function deleteStaff(id) {
  if (!confirm('Delete this staff member?')) return
  try {
    await api.delete(`/staff/${id}`)
    staff.value = staff.value.filter(s => s.id !== id)
    toast.success("Xodim o'chirildi")
  } catch (e) {
    toast.error(e, "Xodimni o'chirib bo'lmadi")
  }
}

async function fetchStaff() {
  loading.value = true
  loadError.value = false
  try {
    const { data } = await api.get('/staff')
    staff.value = data.map(s => ({ ...s, avatar: s.avatar || '' }))
  } catch (e) {
    staff.value = []
    loadError.value = true
    toast.error(e, "Xodimlarni yuklab bo'lmadi")
  } finally { loading.value = false }
}

onMounted(fetchStaff)
</script>

<style scoped>
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
.dropdown-enter-active { transition: all .15s ease-out; }
.dropdown-leave-active { transition: all .1s ease-in; }
.dropdown-enter-from { opacity: 0; transform: translateY(-6px) scale(.97); }
.dropdown-leave-to { opacity: 0; }
</style>