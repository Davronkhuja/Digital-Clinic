<template>
  <div class="min-h-screen bg-slate-50 text-slate-900">
    <header class="bg-white border-b border-slate-200">
      <div class="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between gap-3">
        <h1 class="font-semibold text-base sm:text-lg">{{ t('title') }}</h1>
        <div class="flex items-center gap-3">
          <div class="flex rounded-lg border border-slate-200 overflow-hidden text-xs" role="group" aria-label="Til / Язык">
            <button v-for="l in ['uz', 'ru']" :key="l" type="button" :data-testid="`lang-${l}`" :class="['px-2.5 py-1', lang === l ? 'bg-cyan-600 text-white' : 'bg-white text-slate-500']" @click="setLang(l)">{{ l === 'uz' ? "O'zb" : 'Рус' }}</button>
          </div>
          <button v-if="session" type="button" class="text-xs text-slate-500 underline" data-testid="portal-logout" @click="logout">{{ t('logout') }}</button>
        </div>
      </div>
    </header>

    <main class="max-w-2xl mx-auto px-4 py-5 space-y-4">
      <p v-if="error" class="rounded-xl bg-red-50 text-red-700 text-sm px-4 py-2.5" role="alert" data-testid="portal-error">{{ error }}</p>

      <!-- Kirish: telefon -->
      <form v-if="!session && step === 0" class="bg-white rounded-2xl shadow-sm p-5 space-y-3" @submit.prevent="sendCode">
        <p class="text-sm text-slate-500">{{ t('phone_hint') }}</p>
        <input v-model="phone" required inputmode="tel" autocomplete="tel" placeholder="+998 90 123 45 67" data-testid="portal-phone" class="w-full border border-slate-300 rounded-xl px-3 py-3 text-base" />
        <input v-model="website" tabindex="-1" autocomplete="off" class="hidden" aria-hidden="true" />
        <button class="w-full py-3 rounded-xl bg-cyan-600 text-white font-medium disabled:opacity-50" :disabled="busy" data-testid="portal-send">{{ t('send_code') }}</button>
      </form>

      <!-- Kirish: OTP -->
      <form v-else-if="!session && step === 1" class="bg-white rounded-2xl shadow-sm p-5 space-y-3" @submit.prevent="verify">
        <p class="text-sm text-slate-500">{{ t('code_sent', { phone }) }}</p>
        <input v-model="code" required inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="••••••" data-testid="portal-code" class="w-full border border-slate-300 rounded-xl px-3 py-3 text-xl tracking-[0.4em] text-center" />
        <button class="w-full py-3 rounded-xl bg-emerald-600 text-white font-medium disabled:opacity-50" :disabled="busy" data-testid="portal-verify">{{ t('login') }}</button>
        <button type="button" class="w-full text-xs text-slate-500 underline" @click="step = 0; code = ''; error = ''">{{ t('back') }}</button>
      </form>

      <template v-else-if="session">
        <div v-if="patients.length > 1" class="flex gap-2 overflow-x-auto pb-1">
          <button v-for="p in patients" :key="p.id" type="button" :class="['shrink-0 px-3 py-1.5 rounded-full text-sm border', p.id === patientId ? 'bg-cyan-600 text-white border-cyan-600' : 'bg-white border-slate-300']" @click="pickPatient(p.id)">{{ p.name }}</button>
        </div>
        <p v-else class="text-sm text-slate-500" data-testid="portal-patient">{{ patients[0]?.name }}</p>

        <nav class="grid grid-cols-4 gap-1 bg-slate-200 rounded-xl p-1" role="tablist">
          <button v-for="k in tabs" :key="k" type="button" role="tab" :aria-selected="tab === k" :data-testid="`tab-${k}`" :class="['py-2 rounded-lg text-sm', tab === k ? 'bg-white shadow-sm font-medium' : 'text-slate-600']" @click="openTab(k)">{{ t(k) }}</button>
        </nav>

        <p v-if="loading" class="text-center text-sm text-slate-400 py-6">{{ t('loading') }}</p>

        <section v-else-if="tab === 'appointments'" class="space-y-3" data-testid="portal-appointments">
          <p v-if="!appointments.length" class="text-center text-sm text-slate-400 py-6">{{ t('empty') }}</p>
          <article v-for="a in appointments" :key="a.id" class="bg-white rounded-2xl shadow-sm p-4 space-y-2">
            <div class="flex items-start justify-between gap-2">
              <div>
                <p class="font-semibold">{{ a.date }} · {{ a.time }}</p>
                <p class="text-sm text-slate-500">{{ a.doctor }} · {{ a.type }}</p>
                <p v-if="a.branch" class="text-xs text-slate-400" data-testid="portal-branch">{{ a.branch }}</p>
              </div>
              <span :class="['text-xs px-2 py-0.5 rounded-full', statusClass[a.status] || 'bg-slate-100 text-slate-600']">{{ t('st_' + a.status) }}</span>
            </div>
            <p v-if="a.confirmed && a.can_act" class="text-xs text-emerald-600">{{ t('confirmed') }}</p>
            <div v-if="a.can_act" class="flex gap-2">
              <button v-if="!a.confirmed" type="button" class="flex-1 py-2 rounded-xl bg-emerald-600 text-white text-sm" :disabled="busy" @click="act(a, 'confirm')">{{ t('confirm') }}</button>
              <button type="button" class="flex-1 py-2 rounded-xl border border-red-300 text-red-600 text-sm" :disabled="busy" data-testid="portal-cancel" @click="cancelAsk = a.id">{{ t('cancel') }}</button>
            </div>
            <div v-if="cancelAsk === a.id" class="rounded-xl bg-red-50 p-3 space-y-2 text-sm">
              <p>{{ t('cancel_ask') }}</p>
              <div class="flex gap-2">
                <button type="button" class="flex-1 py-2 rounded-lg bg-red-600 text-white" :disabled="busy" data-testid="portal-cancel-yes" @click="act(a, 'cancel')">{{ t('yes_cancel') }}</button>
                <button type="button" class="flex-1 py-2 rounded-lg bg-white border border-slate-300" @click="cancelAsk = null">{{ t('no') }}</button>
              </div>
            </div>
          </article>
        </section>

        <section v-else-if="tab === 'invoices'" class="space-y-3" data-testid="portal-invoices">
          <p v-if="!invoices.length" class="text-center text-sm text-slate-400 py-6">{{ t('empty') }}</p>
          <article v-for="i in invoices" :key="i.id" class="bg-white rounded-2xl shadow-sm p-4 space-y-1">
            <div class="flex justify-between gap-2"><p class="font-semibold">{{ i.number }}</p><span class="text-xs text-slate-500">{{ i.date }}</span></div>
            <p class="text-sm">{{ t('total') }}: <b>{{ money(i.total) }}</b> · {{ t('paid') }}: {{ money(i.paid) }}</p>
            <p :class="['text-sm', i.balance > 0 ? 'text-amber-600' : 'text-emerald-600']">{{ i.balance > 0 ? t('balance') + ': ' + money(i.balance) : t('settled') }}</p>
          </article>
        </section>

        <section v-else-if="tab === 'book'" class="bg-white rounded-2xl shadow-sm p-4 space-y-3" data-testid="portal-book">
          <p v-if="bookDone" class="rounded-xl bg-emerald-50 text-emerald-700 text-sm px-3 py-2" data-testid="portal-book-done">{{ t('book_done', bookDone) }}</p>
          <div v-if="branches.length > 1"><label class="text-xs text-slate-500">{{ t('branch') }}</label>
            <select v-model="bk.branch_id" class="w-full border border-slate-300 rounded-xl px-3 py-2.5" data-testid="portal-book-branch" @change="onBranch"><option v-for="b in branches" :key="b.id" :value="b.id">{{ b.name }}</option></select></div>
          <div><label class="text-xs text-slate-500">{{ t('service') }}</label>
            <select v-model="bk.type" class="w-full border border-slate-300 rounded-xl px-3 py-2.5" data-testid="portal-book-type"><option v-for="x in types" :key="x.name" :value="x.name">{{ x.name }}</option></select></div>
          <div><label class="text-xs text-slate-500">{{ t('doctor') }}</label>
            <select v-model="bk.doctor_id" class="w-full border border-slate-300 rounded-xl px-3 py-2.5" data-testid="portal-book-doctor" @change="loadSlots"><option value="" disabled>—</option><option v-for="d in doctors" :key="d.id" :value="d.id">{{ d.name }}</option></select></div>
          <div><label class="text-xs text-slate-500">{{ t('date') }}</label>
            <input v-model="bk.date" type="date" :min="minDate" :max="maxDate" class="w-full border border-slate-300 rounded-xl px-3 py-2.5" data-testid="portal-book-date" @change="loadSlots" /></div>
          <p v-if="bk.date && bk.doctor_id && !slots.length && !slotsLoading" class="text-sm text-amber-600">{{ t('no_slots') }}</p>
          <div class="flex flex-wrap gap-2"><button v-for="sl in slots" :key="sl" type="button" :class="['px-3 py-1.5 rounded-lg border text-sm font-mono', bk.time === sl ? 'bg-cyan-600 text-white border-cyan-600' : 'border-slate-300']" data-testid="portal-slot" @click="bk.time = sl">{{ sl }}</button></div>
          <button type="button" class="w-full py-3 rounded-xl bg-cyan-600 text-white font-medium disabled:opacity-50" :disabled="busy || !bk.time" data-testid="portal-book-save" @click="book">{{ t('book_btn') }}</button>
        </section>

        <section v-else class="space-y-3" data-testid="portal-lab">
          <p v-if="!labs.length" class="text-center text-sm text-slate-400 py-6">{{ t('lab_empty') }}</p>
          <article v-for="o in labs" :key="o.id" class="bg-white rounded-2xl shadow-sm p-4 space-y-2">
            <div class="flex justify-between gap-2 items-center">
              <p class="font-semibold">{{ o.date }} <span class="text-sm font-normal text-slate-500">· {{ o.doctor }}</span></p>
              <button type="button" class="text-sm px-3 py-1.5 rounded-lg bg-cyan-600 text-white" :disabled="busy" data-testid="portal-lab-pdf" @click="openPdf(o)">PDF</button>
            </div>
            <ul class="text-sm divide-y divide-slate-100">
              <li v-for="(i, n) in o.items" :key="n" class="py-1.5 flex justify-between gap-3">
                <span>{{ i.name }}</span>
                <span :class="i.flag === 'Normal' || !i.flag ? '' : 'text-red-600 font-semibold'">{{ i.value ?? '—' }} <span class="text-slate-400 font-normal">{{ i.unit }}</span> <span class="text-xs text-slate-400 font-normal">({{ i.reference || '—' }})</span></span>
              </li>
            </ul>
          </article>
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

// Bemor seansi klinika xodimi tokenidan alohida: umumiy `api` (xodim tokeni, /login'ga yo'naltirish) ishlatilmaydi.
const http = axios.create({ baseURL: '/api' })
const SS = 'portal_session', PS = 'portal_patient', PL = 'portal_patients'

const T = {
  uz: {
    title: 'Bemor portali', logout: 'Chiqish', phone_hint: "Klinikada ro'yxatdan o'tgan telefon raqamingizni kiriting. SMS orqali kod yuboramiz.",
    send_code: 'Kod yuborish', code_sent: '{phone} raqamiga SMS kod yuborildi.', login: 'Kirish', back: 'Orqaga', loading: 'Yuklanmoqda...',
    appointments: 'Qabullar', invoices: 'Hisoblar', lab: 'Tahlillar', empty: "Hozircha ma'lumot yo'q", lab_empty: "Shifokor tasdiqlagan natija yo'q",
    confirm: 'Tasdiqlayman', confirmed: 'Tasdiqlangan', cancel: 'Bekor qilish', cancel_ask: 'Qabulni bekor qilishni tasdiqlaysizmi? Vaqt boshqa bemorga beriladi.',
    yes_cancel: 'Ha, bekor qilish', no: "Yo'q", total: 'Jami', paid: "To'langan", balance: 'Qarz', settled: "To'langan",
    st_Scheduled: 'Rejalashtirilgan', st_Completed: 'Yakunlangan', st_Cancelled: 'Bekor qilingan', 'st_No Show': 'Kelmagan',
    book: 'Yozilish', branch: 'Filial', service: 'Xizmat', doctor: 'Shifokor', date: 'Sana', no_slots: "Bu kuni bo'sh vaqt yo'q", book_btn: 'Qabulga yozilish',
    book_done: 'Yozildingiz: {date} {time}, {doctor} ({branch})',
    cancelled_ok: 'Qabul bekor qilindi', confirmed_ok: 'Qabul tasdiqlandi', expired: 'Seans tugadi, qayta kiring', failed: "So'rovni bajarib bo'lmadi",
  },
  ru: {
    title: 'Портал пациента', logout: 'Выйти', phone_hint: 'Введите номер телефона, указанный в клинике. Мы отправим код по SMS.',
    send_code: 'Отправить код', code_sent: 'Код отправлен по SMS на номер {phone}.', login: 'Войти', back: 'Назад', loading: 'Загрузка...',
    appointments: 'Приёмы', invoices: 'Счета', lab: 'Анализы', empty: 'Пока нет данных', lab_empty: 'Нет результатов, подтверждённых врачом',
    confirm: 'Подтвердить', confirmed: 'Подтверждено', cancel: 'Отменить', cancel_ask: 'Отменить приём? Время будет предложено другому пациенту.',
    yes_cancel: 'Да, отменить', no: 'Нет', total: 'Итого', paid: 'Оплачено', balance: 'Долг', settled: 'Оплачено',
    st_Scheduled: 'Запланирован', st_Completed: 'Завершён', st_Cancelled: 'Отменён', 'st_No Show': 'Не явился',
    book: 'Запись', branch: 'Филиал', service: 'Услуга', doctor: 'Врач', date: 'Дата', no_slots: 'На этот день нет свободного времени', book_btn: 'Записаться на приём',
    book_done: 'Вы записаны: {date} {time}, {doctor} ({branch})',
    cancelled_ok: 'Приём отменён', confirmed_ok: 'Приём подтверждён', expired: 'Сеанс истёк, войдите снова', failed: 'Не удалось выполнить запрос',
  },
}
const lang = ref(localStorage.getItem('portal_lang') || 'uz')
const t = (k, vars = {}) => (T[lang.value][k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? '')
function setLang(l) { lang.value = l; try { localStorage.setItem('portal_lang', l) } catch { /* ixtiyoriy */ } }

const statusClass = { Scheduled: 'bg-cyan-100 text-cyan-700', Completed: 'bg-emerald-100 text-emerald-700', Cancelled: 'bg-slate-100 text-slate-500', 'No Show': 'bg-red-100 text-red-700' }
const tabs = ['appointments', 'invoices', 'lab', 'book']
const money = v => `${new Intl.NumberFormat('ru-RU').format(v)} ${lang.value === 'ru' ? 'сум' : "so'm"}`

const session = ref(sessionStorage.getItem(SS) || ''), patients = ref([]), patientId = ref(sessionStorage.getItem(PS) || '')
const step = ref(0), phone = ref(''), code = ref(''), website = ref(''), busy = ref(false), loading = ref(false), error = ref('')
const tab = ref('appointments'), cancelAsk = ref(null)
const appointments = ref([]), invoices = ref([]), labs = ref([])
const branches = ref([]), types = ref([]), doctors = ref([]), slots = ref([]), slotsLoading = ref(false), bookDone = ref(null)
const bk = reactive({ branch_id: '', type: '', doctor_id: '', date: '', time: '' })
const iso = d => d.toISOString().slice(0, 10)
const minDate = iso(new Date()), maxDate = iso(new Date(Date.now() + 60 * 864e5))

const auth = () => ({ headers: { Authorization: `Bearer ${session.value}` } })
function fail(e) {
  if (e?.response?.status === 401 && session.value) { logout(); error.value = t('expired'); return }
  error.value = e?.response?.data?.detail || t('failed')
}
function logout() {
  session.value = ''; patients.value = []; patientId.value = ''; step.value = 0; code.value = ''; error.value = ''
  try { sessionStorage.removeItem(SS); sessionStorage.removeItem(PS); sessionStorage.removeItem(PL) } catch { /* ixtiyoriy */ }
}
async function sendCode() {
  busy.value = true; error.value = ''
  try { await http.post('/public/otp/request', { phone: phone.value, purpose: 'portal', language: lang.value, website: website.value }); step.value = 1 } catch (e) { fail(e) } finally { busy.value = false }
}
async function verify() {
  busy.value = true; error.value = ''
  try {
    const { data: v } = await http.post('/public/otp/verify', { phone: phone.value, purpose: 'portal', code: code.value })
    const { data } = await http.post('/portal/login', { token: v.token })
    session.value = data.session; patients.value = data.patients; patientId.value = data.patients[0].id
    try { sessionStorage.setItem(SS, data.session); sessionStorage.setItem(PS, patientId.value); sessionStorage.setItem(PL, JSON.stringify(data.patients)) } catch { /* ixtiyoriy */ }
    await openTab('appointments')
  } catch (e) { fail(e) } finally { busy.value = false }
}
async function restore() {
  // Sahifa yangilanganda seans (brauzer tabi doirasida) saqlanadi
  if (!session.value || !patientId.value) { logout(); return }
  try { patients.value = JSON.parse(sessionStorage.getItem(PL) || '[]') } catch { patients.value = [] }
  if (!patients.value.length) { logout(); return }
  await openTab('appointments')
}
function pickPatient(id) { patientId.value = id; try { sessionStorage.setItem(PS, id) } catch { /* ixtiyoriy */ } openTab(tab.value) }
async function openTab(k) {
  tab.value = k; error.value = ''; cancelAsk.value = null; bookDone.value = null
  if (k === 'book') { await initBooking(); return }
  loading.value = true
  const path = { appointments: 'appointments', invoices: 'invoices', lab: 'lab-results' }[k]
  try {
    const { data } = await http.get(`/portal/${patientId.value}/${path}`, auth())
    if (k === 'appointments') appointments.value = data
    else if (k === 'invoices') invoices.value = data
    else labs.value = data
  } catch (e) { fail(e) } finally { loading.value = false }
}
async function initBooking() {
  loading.value = true
  try {
    if (!branches.value.length) {
      branches.value = (await http.get('/public/booking/branches')).data
      types.value = (await http.get('/public/booking/types')).data
      bk.branch_id = branches.value[0]?.id || ''; bk.type = types.value[0]?.name || ''
    }
    await onBranch()
  } catch (e) { fail(e) } finally { loading.value = false }
}
async function onBranch() {
  bk.doctor_id = ''; bk.time = ''; slots.value = []
  doctors.value = (await http.get('/public/booking/doctors', { params: { branch_id: bk.branch_id || undefined } })).data
}
async function loadSlots() {
  bk.time = ''; slots.value = []
  if (!bk.doctor_id || !bk.date) return
  slotsLoading.value = true; error.value = ''
  try { slots.value = (await http.get('/public/booking/slots', { params: { doctor_id: bk.doctor_id, date: bk.date, type: bk.type, branch_id: bk.branch_id || undefined } })).data.slots } catch (e) { fail(e) } finally { slotsLoading.value = false }
}
async function book() {
  busy.value = true; error.value = ''
  try {
    const { data } = await http.post(`/portal/${patientId.value}/appointments`, { branch_id: bk.branch_id || null, doctor_id: bk.doctor_id, type: bk.type, date: bk.date, time: bk.time }, auth())
    bookDone.value = data; bk.time = ''; await loadSlots()
  } catch (e) { fail(e) } finally { busy.value = false }
}
async function act(a, what) {
  busy.value = true; error.value = ''
  try {
    await http.post(`/portal/${patientId.value}/appointments/${a.id}/${what}`, null, auth())
    cancelAsk.value = null
    await openTab('appointments')
  } catch (e) { fail(e) } finally { busy.value = false }
}
async function openPdf(o) {
  busy.value = true; error.value = ''
  try {
    const { data } = await http.get(`/portal/${patientId.value}/lab-results/${o.id}/pdf`, { ...auth(), responseType: 'blob' })
    window.open(URL.createObjectURL(data), '_blank')
  } catch (e) { fail(e) } finally { busy.value = false }
}
onMounted(restore)
</script>
