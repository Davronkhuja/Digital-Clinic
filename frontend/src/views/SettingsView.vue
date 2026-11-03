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
        <form @submit.prevent="saveSettings" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
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
            <div class="col-span-2">
              <label :class="lbl">Veb-sayt</label>
              <input v-model="settings.website" class="input" placeholder="https://clinic.uz" />
            </div>
            <div class="col-span-2">
              <label :class="lbl">Litsenziya raqami</label>
              <input v-model="settings.license" class="input" placeholder="MH-2024-XXXXX" />
            </div>
          </div>
          <div class="flex items-center justify-between pt-2">
            <Transition name="fade-quick">
              <p v-if="saved" class="flex items-center gap-1.5 text-emerald-500 text-sm">
                <CheckCircle class="w-4 h-4" /> Saqlandi!
              </p>
            </Transition>
            <button type="submit" class="btn-primary ml-auto" :disabled="saving">
              <Save class="w-4 h-4" />{{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- ═══ Rollar ═══ -->
    <div v-if="activeTab === 'roles'" class="space-y-4">
      <div class="flex items-center justify-between">
        <p :class="['text-sm', dark ? 'text-slate-400' : 'text-slate-500']">Foydalanuvchi rollarini va ruxsatlarini boshqaring</p>
        <button class="btn-primary text-sm" @click="openAddRole"><Plus class="w-4 h-4" /> Yangi rol</button>
      </div>
      <div class="space-y-3">
        <div v-for="role in roles" :key="role.id" class="card p-5">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-center gap-3">
              <div :class="['w-10 h-10 rounded-xl flex items-center justify-center', role.bg]">
                <Shield class="w-5 h-5" :class="role.color" />
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <h4 :class="['font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ role.name }}</h4>
                  <span :class="['badge text-[10px]', role.badgeCls]">{{ role.key }}</span>
                </div>
                <p :class="['text-sm mt-0.5', dark ? 'text-slate-400' : 'text-slate-500']">{{ role.desc }}</p>
              </div>
            </div>
            <div class="flex gap-1 flex-shrink-0">
              <button @click="openEditRole(role)" :class="['p-1.5 rounded-lg transition-colors', dark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-100']"><Pencil class="w-3.5 h-3.5" /></button>
              <button v-if="!role.system" @click="deleteRole(role.id)" class="p-1.5 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"><Trash2 class="w-3.5 h-3.5" /></button>
            </div>
          </div>
          <div class="mt-3 flex flex-wrap gap-1.5">
            <span v-for="p in role.permissions" :key="p" :class="['px-2 py-0.5 rounded-lg text-xs font-medium', dark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600']">{{ p }}</span>
          </div>
        </div>
      </div>

      <Transition name="modal-fade">
        <div v-if="showRoleModal" class="modal-overlay" @click.self="showRoleModal=false">
          <div :class="['w-full max-w-lg rounded-2xl shadow-2xl animate-fade-in', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
            <div :class="['flex items-center justify-between px-6 py-4 border-b', dark ? 'border-slate-800' : 'border-slate-200']">
              <h3 :class="['font-semibold', dark ? 'text-white' : 'text-slate-900']">{{ editingRole ? 'Rolni tahrirlash' : 'Yangi rol' }}</h3>
              <button @click="showRoleModal=false" :class="['p-1.5 rounded-lg', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><X class="w-4 h-4" /></button>
            </div>
            <div class="p-6 space-y-4">
              <div class="grid grid-cols-2 gap-3">
                <div><label :class="lbl">Nomi *</label><input v-model="roleForm.name" class="input" /></div>
                <div><label :class="lbl">Kod</label><input v-model="roleForm.key" class="input" /></div>
              </div>
              <div><label :class="lbl">Tavsif</label><input v-model="roleForm.desc" class="input" /></div>
              <div>
                <label :class="['text-sm font-medium mb-2 block', dark ? 'text-slate-300' : 'text-slate-700']">Ruxsatlar</label>
                <div class="grid grid-cols-2 gap-2">
                  <label v-for="p in allPerms" :key="p" @click="togglePerm(p)"
                    :class="['flex items-center gap-2 p-2.5 rounded-xl cursor-pointer border transition-all',
                      roleForm.permissions.includes(p)
                        ? dark ? 'border-cyan-500/50 bg-cyan-500/10' : 'border-cyan-300 bg-cyan-50'
                        : dark ? 'border-slate-700 hover:border-slate-600' : 'border-slate-200 hover:border-slate-300']">
                    <div :class="['w-4 h-4 rounded flex items-center justify-center flex-shrink-0', roleForm.permissions.includes(p) ? 'bg-cyan-500' : dark ? 'bg-slate-700 border border-slate-600' : 'bg-white border border-slate-300']">
                      <Check v-if="roleForm.permissions.includes(p)" class="w-2.5 h-2.5 text-white" />
                    </div>
                    <span :class="['text-xs font-medium', dark ? 'text-slate-300' : 'text-slate-700']">{{ p }}</span>
                  </label>
                </div>
              </div>
              <div class="flex gap-3 pt-1">
                <button class="btn-secondary flex-1" @click="showRoleModal=false">Bekor</button>
                <button class="btn-primary flex-1" @click="saveRole"><Save class="w-4 h-4" />Saqlash</button>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <!-- ═══ Bildirishnomalar ═══ -->
    <div v-if="activeTab === 'notifications'" class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div class="card p-6">
        <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">Bildirishnoma turlari</h3>
        <div class="space-y-3">
          <div v-for="n in notifSettings" :key="n.key" :class="['flex items-center justify-between p-3.5 rounded-xl border', dark ? 'border-slate-800 bg-slate-800/30' : 'border-slate-100 bg-slate-50']">
            <div class="flex items-center gap-3">
              <div :class="['w-9 h-9 rounded-xl flex items-center justify-center text-base', n.bg]">{{ n.icon }}</div>
              <div>
                <p :class="['text-sm font-medium', dark ? 'text-slate-200' : 'text-slate-800']">{{ n.label }}</p>
                <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">{{ n.desc }}</p>
              </div>
            </div>
            <button @click="n.enabled = !n.enabled"
              :class="['relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0', n.enabled ? 'bg-cyan-500' : dark ? 'bg-slate-600' : 'bg-slate-300']">
              <span :class="['absolute top-[3px] w-[18px] h-[18px] rounded-full bg-white shadow transition-all duration-300', n.enabled ? 'translate-x-[22px]' : 'translate-x-[3px]']"></span>
            </button>
          </div>
        </div>
      </div>
      <div class="card p-6">
        <h3 :class="['font-heading font-semibold mb-4', dark ? 'text-white' : 'text-slate-900']">Yuborish kanallari</h3>
        <div class="space-y-3">
          <div v-for="ch in channels" :key="ch.key" :class="['flex items-center justify-between p-3.5 rounded-xl border', dark ? 'border-slate-800 bg-slate-800/30' : 'border-slate-100 bg-slate-50']">
            <div class="flex items-center gap-3">
              <component :is="ch.icon" :class="['w-5 h-5', ch.color]" />
              <div>
                <p :class="['text-sm font-medium', dark ? 'text-slate-300' : 'text-slate-700']">{{ ch.label }}</p>
                <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">{{ ch.desc }}</p>
              </div>
            </div>
            <button @click="ch.enabled = !ch.enabled"
              :class="['relative w-11 h-6 rounded-full transition-all duration-300', ch.enabled ? 'bg-cyan-500' : dark ? 'bg-slate-600' : 'bg-slate-300']">
              <span :class="['absolute top-[3px] w-[18px] h-[18px] rounded-full bg-white shadow transition-all duration-300', ch.enabled ? 'translate-x-[22px]' : 'translate-x-[3px]']"></span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Building2, Shield, Bell, Check, Save, Plus, X, Pencil, Trash2, CheckCircle, Mail, Smartphone, Monitor } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'

const theme = useThemeStore()
const dark = computed(() => theme.isDark)
const lbl = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])

const activeTab = ref('clinic')
const tabs = [
  { key: 'clinic', label: 'Klinika', icon: Building2 },
  { key: 'roles', label: 'Rollar', icon: Shield },
  { key: 'notifications', label: 'Bildirishnomalar', icon: Bell },
]

// Clinic
const toast = useToast()
const saving = ref(false), saved = ref(false)
const settings = reactive({ clinic_name: 'Digital Clinic', phone: '+998 71 200 0000', email: 'info@digitalclinic.uz', address: "Toshkent, Amir Temur ko'chasi 1", website: '', license: '' })

async function saveSettings() {
  saving.value = true
  try {
    await api.put('/settings', settings)
    saved.value = true
    setTimeout(() => saved.value = false, 2500)
  } catch (e) {
    toast.error(e, "Sozlamalarni saqlab bo'lmadi")
  } finally {
    saving.value = false
  }
}
onMounted(async () => { try { const { data } = await api.get('/settings'); Object.assign(settings, data) } catch (e) { toast.error(e, "Sozlamalarni yuklab bo'lmadi") } })

// Roles
const showRoleModal = ref(false), editingRole = ref(null)
const roleForm = reactive({ name: '', key: '', desc: '', permissions: [] })
const allPerms = ['Dashboard', 'Bemorlar', 'Qabullar', 'EMR', 'Moliya', 'Tahlil', 'AI', 'Hisobotlar', 'Xodimlar', 'Sozlamalar']

const roles = ref([
  { id: 1, name: 'Egasi', key: 'owner', desc: "To'liq huquqlar", system: true, bg: 'bg-amber-50 dark:bg-amber-900/20', color: 'text-amber-500', badgeCls: 'badge-yellow', permissions: allPerms },
  { id: 2, name: 'Admin', key: 'admin', desc: 'Boshqaruv huquqlari', system: true, bg: 'bg-blue-50', color: 'text-blue-500', badgeCls: 'badge-blue', permissions: ['Dashboard', 'Bemorlar', 'Moliya', 'Sozlamalar'] },
  { id: 3, name: 'Shifokor', key: 'doctor', desc: 'Tibbiy huquqlar', system: true, bg: 'bg-emerald-50', color: 'text-emerald-500', badgeCls: 'badge-green', permissions: ['Dashboard', 'Bemorlar', 'Qabullar', 'EMR'] },
  { id: 4, name: 'Kassir', key: 'cashier', desc: 'Moliyaviy huquqlar', system: false, bg: 'bg-purple-50', color: 'text-purple-500', badgeCls: 'badge-slate', permissions: ['Dashboard', 'Moliya'] },
])

function openAddRole() { editingRole.value = null; Object.assign(roleForm, { name: '', key: '', desc: '', permissions: [] }); showRoleModal.value = true }
function openEditRole(r) { editingRole.value = r; Object.assign(roleForm, { name: r.name, key: r.key, desc: r.desc, permissions: [...r.permissions] }); showRoleModal.value = true }
function togglePerm(p) { const i = roleForm.permissions.indexOf(p); i >= 0 ? roleForm.permissions.splice(i, 1) : roleForm.permissions.push(p) }
function saveRole() {
  if (editingRole.value) Object.assign(editingRole.value, { name: roleForm.name, key: roleForm.key, desc: roleForm.desc, permissions: [...roleForm.permissions] })
  else roles.value.push({ id: Date.now(), name: roleForm.name, key: roleForm.key, desc: roleForm.desc, system: false, bg: 'bg-slate-50', color: 'text-slate-500', badgeCls: 'badge-slate', permissions: [...roleForm.permissions] })
  showRoleModal.value = false
}
function deleteRole(id) { if (confirm("O'chirishni tasdiqlaysizmi?")) roles.value = roles.value.filter(r => r.id !== id) }

// Notifications
const notifSettings = ref([
  { key: 'new_patient', icon: '👤', bg: 'bg-blue-100', label: 'Yangi bemor', desc: "Bemor qo'shilganda", enabled: true },
  { key: 'appointment', icon: '📅', bg: 'bg-purple-100', label: 'Uchrashuv', desc: 'Yangi qabul yaratilganda', enabled: true },
  { key: 'payment', icon: '💰', bg: 'bg-emerald-100', label: "To'lov", desc: "To'lov olganda", enabled: true },
  { key: 'cancel', icon: '⚠️', bg: 'bg-amber-100', label: 'Bekor qilish', desc: 'Qabul bekor bo\'lganda', enabled: true },
  { key: 'emr', icon: '📋', bg: 'bg-cyan-100', label: 'EMR', desc: 'Yozuv yangilanganda', enabled: false },
])
const channels = ref([
  { key: 'inapp', label: 'Tizim ichida', desc: 'Brauzer bildirgi', icon: Monitor, color: 'text-blue-500', enabled: true },
  { key: 'email', label: 'Email', desc: 'Elektron pochta orqali', icon: Mail, color: 'text-emerald-500', enabled: true },
  { key: 'sms', label: 'SMS', desc: 'Telefon xabari', icon: Smartphone, color: 'text-purple-500', enabled: false },
])
</script>

<style scoped>
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
.fade-quick-enter-active { transition: opacity .3s; }
.fade-quick-leave-active { transition: opacity .2s; }
.fade-quick-enter-from, .fade-quick-leave-to { opacity: 0; }
</style>