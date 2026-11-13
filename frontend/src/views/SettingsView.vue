<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Sozlamalar</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Klinika va tizim sozlamalari</p>
    </div>

    <!-- Tabs -->
    <div :class="['flex gap-1 p-1 rounded-xl w-fit border', dark ? 'bg-slate-800/50 border-slate-700' : 'bg-slate-100 border-slate-200']">
      <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
        :class="['flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
          activeTab === tab.key
            ? dark ? 'bg-slate-700 text-white shadow-sm' : 'bg-white text-slate-900 shadow-sm'
            : dark ? 'text-slate-400 hover:text-slate-300' : 'text-slate-600 hover:text-slate-800']">
        <component :is="tab.icon" class="w-4 h-4" />{{ tab.label }}
      </button>
    </div>

    <!-- ═══ Klinika ═══ -->
    <div v-if="activeTab === 'clinic'" class="max-w-2xl">
      <div class="card p-6">
        <h3 :class="['font-heading font-semibold mb-5', dark ? 'text-white' : 'text-slate-900']">Klinika ma'lumotlari</h3>
        <div v-if="loadingSettings" :class="['text-sm py-8 text-center', dark ? 'text-slate-400' : 'text-slate-500']">Yuklanmoqda...</div>
        <form v-else @submit.prevent="saveSettings" class="space-y-4">
          <fieldset :disabled="!canWrite" class="grid grid-cols-2 gap-4">
            <div class="col-span-2">
              <label :class="lbl">Klinika nomi</label>
              <input v-model="settings.clinic_name" class="input" />
            </div>
            <div>
              <label :class="lbl">Telefon</label>
              <input v-model="settings.phone" class="input" />
            </div>
            <div>
              <label :class="lbl">Email</label>
              <input v-model="settings.email" type="email" class="input" />
            </div>
            <div class="col-span-2">
              <label :class="lbl">Manzil</label>
              <input v-model="settings.address" class="input" />
            </div>
            <div>
              <label :class="lbl">Valyuta</label>
              <input v-model="settings.currency" class="input" />
            </div>
            <div>
              <label :class="lbl">Vaqt mintaqasi</label>
              <input v-model="settings.timezone" class="input" />
            </div>
            <div class="col-span-2">
              <label :class="lbl">Til</label>
              <input v-model="settings.language" class="input" />
            </div>
          </fieldset>
          <div v-if="canWrite" class="flex items-center justify-end pt-2">
            <button type="submit" class="btn-primary" :disabled="saving">
              <Save class="w-4 h-4" />{{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
            </button>
          </div>
          <p v-else :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">Sozlamalarni o'zgartirish uchun ruxsatingiz yo'q (faqat o'qish).</p>
        </form>
      </div>
    </div>

    <!-- ═══ Rollar ═══ -->
    <MessagingSettings v-if="activeTab === 'messaging' && canResources" />
    <FinanceSettings v-if="activeTab === 'finance' && canResources" />
    <ServiceCatalog v-if="activeTab === 'services' && auth.can('services:read')" />
    <BranchesSettings v-if="activeTab === 'branches' && auth.can('branches:manage')" />
    <LabCatalog v-if="activeTab === 'lab' && canResources" />
    <ExamTemplates v-if="activeTab === 'templates' && auth.can('emr:write')" />
    <ClinicResources v-if="activeTab === 'resources' && canResources" />

    <div v-if="activeTab === 'roles'" class="space-y-4">
      <p :class="['text-sm', dark ? 'text-slate-400' : 'text-slate-500']">Rollarning ruxsatlarini boshqaring</p>
      <div v-if="loadingRoles" :class="['text-sm py-8 text-center', dark ? 'text-slate-400' : 'text-slate-500']">Yuklanmoqda...</div>
      <EmptyState v-else-if="!roles.length" title="Rollar topilmadi" />
      <div v-else class="space-y-3">
        <div v-for="role in roles" :key="role.id" class="card p-5">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-center gap-3">
              <div :class="['w-10 h-10 rounded-xl flex items-center justify-center', dark ? 'bg-slate-800' : 'bg-blue-50']">
                <Shield class="w-5 h-5 text-blue-500" />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <h4 :class="['font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ role.name }}</h4>
                  <span class="badge badge-blue text-[10px]">{{ role.code }}</span>
                </div>
                <p :class="['text-sm mt-0.5', dark ? 'text-slate-400' : 'text-slate-500']">
                  Foydalanuvchilar: {{ role.users_count }}<template v-if="role.code === 'admin'"> · Administrator roli o'zgarmaydi</template>
                </p>
              </div>
            </div>
            <div v-if="role.code !== 'admin'" class="flex gap-1 flex-shrink-0">
              <button @click="openEditRole(role)" :class="['p-1.5 rounded-lg transition-colors', dark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-100']"><Pencil class="w-3.5 h-3.5" /></button>
            </div>
          </div>
          <div class="mt-3 flex flex-wrap gap-1.5">
            <span v-for="p in role.permissions" :key="p" :class="['px-2 py-0.5 rounded-lg text-xs font-medium', dark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600']">{{ p }}</span>
          </div>
        </div>
      </div>

      <Transition name="modal-fade">
        <div v-if="showRoleModal" class="modal-overlay" @click.self="showRoleModal=false">
          <div :class="['w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl animate-fade-in', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
            <div :class="['flex items-center justify-between px-6 py-4 border-b', dark ? 'border-slate-800' : 'border-slate-200']">
              <h3 :class="['font-semibold', dark ? 'text-white' : 'text-slate-900']">Rolni tahrirlash</h3>
              <button @click="showRoleModal=false" :class="['p-1.5 rounded-lg', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><X class="w-4 h-4" /></button>
            </div>
            <div class="p-6 space-y-4">
              <div><label :class="lbl">Nomi *</label><input v-model="roleForm.name" class="input" /></div>
              <div>
                <label :class="['text-sm font-medium mb-2 block', dark ? 'text-slate-300' : 'text-slate-700']">Ruxsatlar</label>
                <div class="space-y-3">
                  <div v-for="group in permGroups" :key="group.name">
                    <p :class="['text-[11px] uppercase tracking-wider font-semibold mb-1.5', dark ? 'text-slate-500' : 'text-slate-400']">{{ group.name }}</p>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <label v-for="p in group.items" :key="p.code" @click.prevent="togglePerm(p.code)"
                        :class="['flex items-center gap-2 p-2.5 rounded-xl cursor-pointer border transition-all',
                          roleForm.permissions.includes(p.code)
                            ? dark ? 'border-cyan-500/50 bg-cyan-500/10' : 'border-cyan-300 bg-cyan-50'
                            : dark ? 'border-slate-700 hover:border-slate-600' : 'border-slate-200 hover:border-slate-300']">
                        <div :class="['w-4 h-4 rounded flex items-center justify-center flex-shrink-0', roleForm.permissions.includes(p.code) ? 'bg-cyan-500' : dark ? 'bg-slate-700 border border-slate-600' : 'bg-white border border-slate-300']">
                          <Check v-if="roleForm.permissions.includes(p.code)" class="w-2.5 h-2.5 text-white" />
                        </div>
                        <span>
                          <span :class="['block text-xs font-medium', dark ? 'text-slate-300' : 'text-slate-700']">{{ p.description || p.code }}</span>
                          <span :class="['block text-[10px] font-mono', dark ? 'text-slate-500' : 'text-slate-400']">{{ p.code }}</span>
                        </span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>
              <div class="flex gap-3 pt-1">
                <button class="btn-secondary flex-1" @click="showRoleModal=false">Bekor</button>
                <button class="btn-primary flex-1" :disabled="savingRole || !roleForm.name.trim()" @click="saveRole"><Save class="w-4 h-4" />{{ savingRole ? 'Saqlanmoqda...' : 'Saqlash' }}</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <!-- ═══ Foydalanuvchilar ═══ -->
    <div v-if="activeTab === 'users'" class="space-y-4">
      <div class="flex items-center justify-between">
        <p :class="['text-sm', dark ? 'text-slate-400' : 'text-slate-500']">Tizim foydalanuvchilari va ularning rollari</p>
        <button class="btn-primary text-sm" @click="openAddUser"><Plus class="w-4 h-4" /> Xodim qo'shish</button>
      </div>
      <div v-if="loadingUsers" :class="['text-sm py-8 text-center', dark ? 'text-slate-400' : 'text-slate-500']">Yuklanmoqda...</div>
      <EmptyState v-else-if="!users.length" title="Foydalanuvchilar yo'q" description="Yangi xodim qo'shing" />
      <div v-else class="card overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr :class="['text-left text-xs uppercase tracking-wider', dark ? 'text-slate-500' : 'text-slate-400']">
              <th class="px-4 py-3 font-semibold">Ism</th>
              <th class="px-4 py-3 font-semibold">Email</th>
              <th class="px-4 py-3 font-semibold">Rol</th>
              <th class="px-4 py-3 font-semibold">Filial</th>
              <th class="px-4 py-3 font-semibold">Oxirgi kirish</th>
              <th class="px-4 py-3 font-semibold">Faol</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" :class="['border-t', dark ? 'border-slate-800' : 'border-slate-100']">
              <td :class="['px-4 py-3 font-medium', dark ? 'text-white' : 'text-slate-900']">{{ u.name }}</td>
              <td :class="['px-4 py-3', dark ? 'text-slate-300' : 'text-slate-600']">{{ u.email }}</td>
              <td class="px-4 py-3">
                <select :value="u.role" class="input !py-1.5 !w-auto" @change="changeRole(u, $event)">
                  <option v-for="r in roleOptions" :key="r.code" :value="r.code">{{ r.name }}</option>
                </select>
              </td>
              <td class="px-4 py-3">
                <select v-if="auth.can('branches:manage') && branchOptions.length > 1" :value="u.branch_id" class="input !py-1.5 !w-auto" data-testid="user-branch" @change="changeBranch(u, $event)">
                  <option v-for="b in branchOptions" :key="b.id" :value="b.id">{{ b.name }}</option>
                </select>
                <span v-else :class="dark ? 'text-slate-300' : 'text-slate-600'">{{ u.branch || '—' }}</span>
              </td>
              <td :class="['px-4 py-3', dark ? 'text-slate-400' : 'text-slate-500']">{{ formatDate(u.last_login_at) }}</td>
              <td class="px-4 py-3">
                <button @click="toggleActive(u)"
                  :class="['relative w-11 h-6 rounded-full transition-all duration-300', u.is_active ? 'bg-cyan-500' : dark ? 'bg-slate-600' : 'bg-slate-300']">
                  <span :class="['absolute top-[3px] w-[18px] h-[18px] rounded-full bg-white shadow transition-all duration-300', u.is_active ? 'translate-x-[22px]' : 'translate-x-[3px]']"></span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <Transition name="modal-fade">
        <div v-if="showUserModal" class="modal-overlay" @click.self="showUserModal=false">
          <div :class="['w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl shadow-2xl animate-fade-in', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
            <div :class="['flex items-center justify-between px-6 py-4 border-b', dark ? 'border-slate-800' : 'border-slate-200']">
              <h3 :class="['font-semibold', dark ? 'text-white' : 'text-slate-900']">Xodim qo'shish</h3>
              <button @click="showUserModal=false" :class="['p-1.5 rounded-lg', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><X class="w-4 h-4" /></button>
            </div>
            <form @submit.prevent="saveUser" class="p-6 space-y-4">
              <div><label :class="lbl">Ism *</label><input v-model="userForm.name" class="input" required /></div>
              <div class="grid grid-cols-2 gap-3">
                <div><label :class="lbl">Email *</label><input v-model="userForm.email" type="email" class="input" required /></div>
                <div><label :class="lbl">Parol * (kamida 8 belgi)</label><input v-model="userForm.password" type="password" minlength="8" class="input" required /></div>
                <div>
                  <label :class="lbl">Rol *</label>
                  <select v-model="userForm.role" class="input">
                    <option v-for="r in roleOptions" :key="r.code" :value="r.code">{{ r.name }}</option>
                  </select>
                </div>
                <div v-if="auth.can('branches:manage') && branchOptions.length > 1">
                  <label :class="lbl">Filial</label>
                  <select v-model="userForm.branch_id" class="input"><option value="">Faol filial</option><option v-for="b in branchOptions" :key="b.id" :value="b.id">{{ b.name }}</option></select>
                </div>
                <div><label :class="lbl">Bo'lim</label><input v-model="userForm.department" class="input" /></div>
                <div class="col-span-2"><label :class="lbl">Telefon</label><input v-model="userForm.phone" class="input" /></div>
              </div>
              <div class="flex gap-3 pt-1">
                <button type="button" class="btn-secondary flex-1" @click="showUserModal=false">Bekor</button>
                <button type="submit" class="btn-primary flex-1" :disabled="savingUser"><Save class="w-4 h-4" />{{ savingUser ? 'Saqlanmoqda...' : 'Saqlash' }}</button>
              </div>
            </form>
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Building2, DoorOpen, FileText, FlaskConical, MessageCircle, Tag, Shield, Users, Check, Save, Plus, X, Pencil } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/ui/EmptyState.vue'
import ClinicResources from '@/components/ClinicResources.vue'
import ExamTemplates from '@/components/ExamTemplates.vue'
import LabCatalog from '@/components/LabCatalog.vue'
import ServiceCatalog from '@/components/ServiceCatalog.vue'
import BranchesSettings from '@/components/BranchesSettings.vue'
import FinanceSettings from '@/components/FinanceSettings.vue'
import MessagingSettings from '@/components/MessagingSettings.vue'

const theme = useThemeStore()
const auth = useAuthStore()
const toast = useToast()
const dark = computed(() => theme.isDark)
const lbl = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])

const canWrite = computed(() => auth.can('settings:write'))
const canManage = computed(() => auth.can('roles:manage'))
const canResources = computed(() => auth.can('settings:write'))

const activeTab = ref('clinic')
const tabs = computed(() => [
  { key: 'clinic', label: 'Klinika', icon: Building2 },
  ...(auth.can('emr:write') ? [{ key: 'templates', label: "Ko'rik shablonlari", icon: FileText }] : []),
  ...(canResources.value ? [{ key: 'messaging', label: 'Xabarlar', icon: MessageCircle }] : []),
  ...(canResources.value ? [{ key: 'finance', label: 'Moliya', icon: Tag }] : []),
  ...(auth.can('services:read') ? [{ key: 'services', label: 'Narxnoma', icon: Tag }] : []),
  ...(auth.can('branches:manage') ? [{ key: 'branches', label: 'Filiallar', icon: Building2 }] : []),
  ...(canResources.value ? [{ key: 'lab', label: "Laboratoriya me'yorlari", icon: FlaskConical }] : []),
  ...(canResources.value ? [{ key: 'resources', label: 'Kabinet va qabul turlari', icon: DoorOpen }] : []),
  ...(canManage.value ? [
    { key: 'roles', label: 'Rollar', icon: Shield },
    { key: 'users', label: 'Foydalanuvchilar', icon: Users },
  ] : []),
])

// Klinika
const loadingSettings = ref(true), saving = ref(false)
const settings = reactive({ clinic_name: '', address: '', phone: '', email: '', currency: '', timezone: '', language: '' })

async function loadSettings() {
  loadingSettings.value = true
  try {
    const { data } = await api.get('/settings')
    Object.keys(settings).forEach(k => { settings[k] = data[k] ?? '' })
  } catch (e) {
    toast.error(e, "Sozlamalarni yuklab bo'lmadi")
  } finally {
    loadingSettings.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    await api.put('/settings', { ...settings })
    toast.success('Sozlamalar saqlandi')
  } catch (e) {
    toast.error(e, "Sozlamalarni saqlab bo'lmadi")
  } finally {
    saving.value = false
  }
}

// Rollar
const roles = ref([]), permissions = ref([])
const loadingRoles = ref(false)
const showRoleModal = ref(false), editingRole = ref(null), savingRole = ref(false)
const roleForm = reactive({ name: '', permissions: [] })
const roleOptions = computed(() => roles.value)

// ruxsat kodlari bo'yicha guruhlash: patients:read -> "patients"
const permGroups = computed(() => {
  const groups = {}
  for (const p of permissions.value) {
    const g = p.code.split(':')[0]
    ;(groups[g] ||= { name: g, items: [] }).items.push(p)
  }
  return Object.values(groups)
})

async function loadRoles() {
  loadingRoles.value = true
  try {
    const [r, p] = await Promise.all([api.get('/roles'), api.get('/permissions')])
    roles.value = r.data
    permissions.value = p.data
  } catch (e) {
    toast.error(e, "Rollarni yuklab bo'lmadi")
  } finally {
    loadingRoles.value = false
  }
}

function openEditRole(r) {
  editingRole.value = r
  Object.assign(roleForm, { name: r.name, permissions: [...r.permissions] })
  showRoleModal.value = true
}
function togglePerm(code) {
  const i = roleForm.permissions.indexOf(code)
  i >= 0 ? roleForm.permissions.splice(i, 1) : roleForm.permissions.push(code)
}
async function saveRole() {
  savingRole.value = true
  try {
    await api.put(`/roles/${editingRole.value.id}`, { name: roleForm.name.trim(), permissions: roleForm.permissions })
    toast.success('Rol saqlandi')
    showRoleModal.value = false
    await loadRoles()
  } catch (e) {
    toast.error(e, "Rolni saqlab bo'lmadi")
  } finally {
    savingRole.value = false
  }
}

// Foydalanuvchilar
const users = ref([])
const loadingUsers = ref(false)
const showUserModal = ref(false), savingUser = ref(false)
const userForm = reactive({ name: '', email: '', password: '', role: 'doctor', department: '', phone: '', branch_id: '' })
const branchOptions = ref([])

async function loadUsers() {
  loadingUsers.value = true
  if (auth.can('branches:manage')) { try { branchOptions.value = (await api.get('/branches')).data } catch { branchOptions.value = [] } }
  try {
    const { data } = await api.get('/users')
    users.value = data
  } catch (e) {
    toast.error(e, "Foydalanuvchilarni yuklab bo'lmadi")
  } finally {
    loadingUsers.value = false
  }
}

function formatDate(v) {
  return v ? new Date(v).toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' }) : '—'
}

function openAddUser() {
  Object.assign(userForm, { name: '', email: '', password: '', role: 'doctor', department: '', phone: '', branch_id: '' })
  showUserModal.value = true
}
async function saveUser() {
  savingUser.value = true
  try {
    const body = { name: userForm.name.trim(), email: userForm.email.trim(), password: userForm.password, role: userForm.role }
    if (userForm.department.trim()) body.department = userForm.department.trim()
    if (userForm.phone.trim()) body.phone = userForm.phone.trim()
    if (userForm.branch_id) body.branch_id = userForm.branch_id
    await api.post('/users', body)
    toast.success("Xodim qo'shildi")
    showUserModal.value = false
    await Promise.all([loadUsers(), loadRoles()])
  } catch (e) {
    toast.error(e, "Xodimni qo'shib bo'lmadi")
  } finally {
    savingUser.value = false
  }
}
async function patchUser(u, body, okMsg) {
  try {
    await api.patch(`/users/${u.id}`, body)
    toast.success(okMsg)
  } catch (e) {
    toast.error(e, "Foydalanuvchini yangilab bo'lmadi")
  }
  await Promise.all([loadUsers(), loadRoles()])
}
function changeBranch(u, ev) { return patchUser(u, { branch_id: ev.target.value }, 'Xodim boshqa filialga biriktirildi') }
function changeRole(u, ev) { return patchUser(u, { role: ev.target.value }, "Rol o'zgartirildi") }
function toggleActive(u) { return patchUser(u, { is_active: !u.is_active }, u.is_active ? "Foydalanuvchi o'chirildi" : 'Foydalanuvchi faollashtirildi') }

onMounted(() => {
  loadSettings()
  if (canManage.value) { loadRoles(); loadUsers() }
})
</script>

<style scoped>
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
.fade-quick-enter-active { transition: opacity .3s; }
.fade-quick-leave-active { transition: opacity .2s; }
.fade-quick-enter-from, .fade-quick-leave-to { opacity: 0; }
</style>