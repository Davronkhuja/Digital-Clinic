<template>
  <div class="min-h-screen flex items-start sm:items-center justify-center p-4 bg-slate-50">
    <div class="w-full max-w-lg bg-white rounded-2xl shadow-lg p-6 space-y-5">
      <h1 class="text-lg font-semibold text-slate-900">Onlayn yozilish</h1>
      <ol class="flex text-xs gap-1 text-slate-400">
        <li v-for="(s, i) in steps" :key="s" :class="['flex-1 text-center py-1 rounded', step === i ? 'bg-cyan-600 text-white' : step > i ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100']">{{ s }}</li>
      </ol>
      <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

      <div v-if="!branchChosen" class="space-y-2" data-testid="book-branches">
        <p class="text-sm text-slate-500">Filialni tanlang</p>
        <button v-for="b in branches" :key="b.id" class="w-full text-left px-4 py-3 rounded-xl border hover:border-cyan-500 text-sm" data-testid="book-branch" @click="pickBranch(b)">{{ b.name }}<span v-if="b.address" class="block text-xs text-slate-400">{{ b.address }}</span></button>
      </div>

      <div v-else-if="step === 0" class="space-y-2">
        <p v-if="branches.length > 1" class="text-xs text-slate-400">Filial: <b>{{ branchName }}</b> · <button class="underline" @click="branchChosen = false">o'zgartirish</button></p>
        <p class="text-sm text-slate-500">Xizmatni tanlang</p>
        <button v-for="t in types" :key="t.name" class="w-full text-left px-4 py-3 rounded-xl border hover:border-cyan-500 text-sm" @click="pickType(t)">{{ t.name }} <span class="text-slate-400">· {{ t.duration_min }} daq</span></button>
      </div>

      <div v-else-if="step === 1" class="space-y-2">
        <p class="text-sm text-slate-500">Shifokorni tanlang</p>
        <button v-for="d in doctors" :key="d.id" class="w-full text-left px-4 py-3 rounded-xl border hover:border-cyan-500 text-sm" @click="pickDoctor(d)">{{ d.name }} <span class="text-slate-400">{{ d.department }}</span></button>
        <button class="text-xs text-slate-400 underline" @click="step = 0">Orqaga</button>
      </div>

      <div v-else-if="step === 2" class="space-y-3">
        <input v-model="date" type="date" :min="minDate" :max="maxDate" class="w-full border rounded-xl px-3 py-2 text-sm" @change="loadSlots" />
        <p v-if="loadingSlots" class="text-sm text-slate-400">Yuklanmoqda...</p>
        <p v-else-if="date && !slots.length" class="text-sm text-amber-600">Bu kuni bo'sh vaqt yo'q.</p>
        <div class="flex flex-wrap gap-2">
          <button v-for="s in slots" :key="s" :class="['px-3 py-1.5 rounded-lg border text-sm font-mono', time === s ? 'bg-cyan-600 text-white border-cyan-600' : 'hover:border-cyan-500']" @click="time = s">{{ s }}</button>
        </div>
        <div class="flex justify-between"><button class="text-xs text-slate-400 underline" @click="step = 1">Orqaga</button><button class="px-4 py-2 rounded-xl bg-cyan-600 text-white text-sm disabled:opacity-50" :disabled="!time" @click="step = 3">Davom etish</button></div>
      </div>

      <form v-else-if="step === 3" class="space-y-3" @submit.prevent="sendCode">
        <input v-model="form.name" required minlength="2" placeholder="Ism familiya" class="w-full border rounded-xl px-3 py-2 text-sm" />
        <input v-model="form.phone" required placeholder="+998 90 123 45 67" class="w-full border rounded-xl px-3 py-2 text-sm" />
        <input v-model="form.birth_date" type="date" class="w-full border rounded-xl px-3 py-2 text-sm" title="Tug'ilgan sana (ixtiyoriy)" />
        <select v-model="form.language" class="w-full border rounded-xl px-3 py-2 text-sm"><option value="uz">O'zbekcha</option><option value="ru">Русский</option></select>
        <label class="flex items-start gap-2 text-xs text-slate-500"><input v-model="form.consent_sms" type="checkbox" class="mt-0.5" /> Eslatma va xabarlarni SMS orqali olishga roziman (istalgan vaqtda voz kechish mumkin).</label>
        <input v-model="form.website" tabindex="-1" autocomplete="off" class="hidden" aria-hidden="true" />
        <div class="flex justify-between"><button type="button" class="text-xs text-slate-400 underline" @click="step = 2">Orqaga</button><button class="px-4 py-2 rounded-xl bg-cyan-600 text-white text-sm disabled:opacity-50" :disabled="busy">Kod yuborish</button></div>
      </form>

      <form v-else-if="step === 4" class="space-y-3" @submit.prevent="verifyAndBook">
        <p class="text-sm text-slate-500">{{ form.phone }} raqamiga SMS kod yuborildi.</p>
        <input v-model="code" required inputmode="numeric" maxlength="6" placeholder="6 raqamli kod" class="w-full border rounded-xl px-3 py-2 text-sm tracking-widest text-center" />
        <button class="w-full px-4 py-2.5 rounded-xl bg-emerald-600 text-white text-sm disabled:opacity-50" :disabled="busy">Tasdiqlash va yozilish</button>
      </form>

      <div v-else-if="step === 5" class="space-y-2 text-center">
        <h2 class="text-lg font-semibold text-emerald-700">Siz yozildingiz</h2>
        <p class="text-sm text-slate-600">{{ result.date }} {{ result.time }}, {{ result.doctor }}</p>
        <a :href="result.manage_link" class="text-sm text-cyan-600 underline">Qabulni tasdiqlash yoki bekor qilish</a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '@/composables/useApi'

const steps = ['Xizmat', 'Shifokor', 'Vaqt', 'Telefon', 'Kod', 'Tayyor']
const step = ref(0), error = ref(''), busy = ref(false), loadingSlots = ref(false)
const types = ref([]), doctors = ref([]), slots = ref([]), result = ref(null)
const branches = ref([]), branchId = ref(''), branchChosen = ref(true)
const branchName = computed(() => branches.value.find(b => b.id === branchId.value)?.name || '')
const type = ref(null), doctor = ref(null), date = ref(''), time = ref(''), code = ref('')
const form = reactive({ name: '', phone: '', birth_date: '', language: 'uz', consent_sms: false, website: '' })
const iso = d => d.toISOString().slice(0, 10)
const minDate = iso(new Date()), maxDate = iso(new Date(Date.now() + 60 * 864e5))
const fail = e => { error.value = e?.response?.data?.detail || "So'rovni bajarib bo'lmadi" }

onMounted(async () => {
  try {
    types.value = (await api.get('/public/booking/types')).data
    branches.value = (await api.get('/public/booking/branches')).data
    if (branches.value.length === 1) branchId.value = branches.value[0].id
    else branchChosen.value = false             // bir nechta filial: avval tanlanadi
  } catch (e) { fail(e) }
})
function pickBranch(b) { branchId.value = b.id; branchChosen.value = true; step.value = 0; error.value = '' }
async function pickType(t) { type.value = t; error.value = ''; try { doctors.value = (await api.get('/public/booking/doctors', { params: { branch_id: branchId.value || undefined } })).data; step.value = 1 } catch (e) { fail(e) } }
function pickDoctor(d) { doctor.value = d; step.value = 2; slots.value = []; date.value = ''; time.value = '' }
async function loadSlots() {
  time.value = ''; error.value = ''; loadingSlots.value = true
  try { slots.value = (await api.get('/public/booking/slots', { params: { doctor_id: doctor.value.id, date: date.value, type: type.value.name, branch_id: branchId.value || undefined } })).data.slots } catch (e) { slots.value = []; fail(e) } finally { loadingSlots.value = false }
}
async function sendCode() {
  busy.value = true; error.value = ''
  try { await api.post('/public/otp/request', { phone: form.phone, purpose: 'booking', language: form.language, website: form.website }); step.value = 4 } catch (e) { fail(e) } finally { busy.value = false }
}
async function verifyAndBook() {
  busy.value = true; error.value = ''
  try {
    const { data } = await api.post('/public/otp/verify', { phone: form.phone, purpose: 'booking', code: code.value })
    result.value = (await api.post('/public/booking', { token: data.token, name: form.name, birth_date: form.birth_date || null, doctor_id: doctor.value.id, type: type.value.name,
      date: date.value, time: time.value, language: form.language, consent_sms: form.consent_sms, website: form.website, branch_id: branchId.value || null })).data
    step.value = 5
  } catch (e) { fail(e) } finally { busy.value = false }
}
</script>
