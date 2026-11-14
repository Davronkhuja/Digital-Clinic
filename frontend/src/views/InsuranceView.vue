<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Sug'urta (DMS)</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Kompaniyalar va shartnomalar, bemor polislari, kafolat xatlari, kompaniya qarzi va oylik reyestr</p>
    </div>

    <div class="card">
      <div :class="['px-4 pt-3 border-b flex gap-1 flex-wrap', dark ? 'border-slate-800' : 'border-slate-100']" role="tablist">
        <button v-for="t in tabs" :key="t.key" role="tab" :data-testid="`ins-tab-${t.key}`" :aria-selected="tab === t.key"
          :class="['px-3 py-2 text-sm rounded-t-lg', tab === t.key ? 'border-b-2 border-cyan-500 font-semibold text-cyan-600' : 'text-slate-500']" @click="tab = t.key">{{ t.label }}</button>
      </div>

      <!-- Kompaniyalar va shartnomalar -->
      <div v-if="tab === 'insurers'" class="p-4 space-y-4" data-testid="ins-insurers">
        <div class="flex justify-between gap-2 flex-wrap">
          <p class="text-sm text-slate-500">Faqat ixtiyoriy tibbiy sug'urta (DMS).</p>
          <span v-if="canManage" class="flex gap-2">
            <button class="btn-secondary text-sm" data-testid="ins-new-insurer" @click="openInsurer()">Kompaniya</button>
            <button class="btn-primary text-sm" data-testid="ins-new-contract" @click="openContract()">Shartnoma</button>
          </span>
        </div>
        <EmptyState v-if="!insurers.length" title="Kompaniya yo'q" description="Avval sug'urta kompaniyasini qo'shing" />
        <div v-for="i in insurers" :key="i.id" class="border rounded-xl p-3 space-y-2" :class="dark ? 'border-slate-800' : 'border-slate-200'">
          <div class="flex justify-between gap-2 flex-wrap items-center">
            <p class="font-semibold">{{ i.name }} <span v-if="i.tin" class="text-xs text-slate-400 font-mono">STIR {{ i.tin }}</span> <span class="text-xs text-slate-400">· to'lov muddati oy oxiridan {{ i.payment_days }} kun</span></p>
            <button v-if="canManage" class="text-xs text-cyan-600 hover:underline" @click="openInsurer(i)">Tahrirlash</button>
          </div>
          <div v-for="c in contractsOf(i.id)" :key="c.id" class="text-sm flex justify-between gap-2 flex-wrap pl-3 border-l-2 border-cyan-200">
            <span><b>{{ c.number }}</b> · {{ c.valid_from }} — {{ c.valid_to || 'muddatsiz' }} · chegirma {{ c.discount_percent }}% · {{ c.coverage_all ? `hamma xizmat ${c.default_coverage_percent}%` : c.services.length + ' ta xizmat' }}
              <span v-if="c.annual_limit != null" class="text-slate-400"> · yillik limit {{ fmt(c.annual_limit) }}</span><span v-if="c.per_visit_limit != null" class="text-slate-400"> · bir hisob-faktura {{ fmt(c.per_visit_limit) }}</span>
              <span v-if="c.requires_guarantee" class="badge-yellow ml-1">kafolat xati kerak</span></span>
            <button v-if="canManage" class="text-xs text-cyan-600 hover:underline" @click="openContract(c)">Tahrirlash</button>
          </div>
          <p v-if="!contractsOf(i.id).length" class="text-xs text-slate-400 pl-3">Shartnoma yo'q</p>
        </div>
      </div>

      <!-- Polislar va kafolat xatlari -->
      <div v-else-if="tab === 'policies'" class="p-4 space-y-5" data-testid="ins-policies">
        <div class="flex gap-2 flex-wrap">
          <input v-model="policySearch" class="input flex-1 min-w-48" placeholder="Polis raqami..." @input="loadPolicies" data-testid="ins-policy-search" />
          <button v-if="canWrite" class="btn-primary text-sm" data-testid="ins-new-policy" @click="openPolicy">Yangi polis</button>
          <button v-if="canWrite" class="btn-secondary text-sm" data-testid="ins-new-letter" @click="openLetter">Kafolat xati</button>
        </div>
        <div class="table-container rounded-none border-0">
          <table class="table text-sm"><thead><tr><th>Bemor</th><th>Kompaniya</th><th>Polis</th><th>Shartnoma</th><th>Muddat</th><th>Holat</th></tr></thead>
            <tbody><tr v-for="p in policies" :key="p.id"><td>{{ p.patient }}</td><td>{{ p.insurer }}</td><td class="font-mono">{{ p.number }}</td><td>{{ p.contract }}</td>
              <td class="text-xs">{{ p.valid_from }} — {{ p.valid_to || 'muddatsiz' }}</td><td><span :class="p.valid_now ? 'badge-green' : 'badge-slate'">{{ p.valid_now ? 'Amal qiladi' : 'Amal qilmaydi' }}</span></td></tr>
              <tr v-if="!policies.length"><td colspan="6" class="text-center text-slate-400 py-4">Polis yo'q</td></tr></tbody></table>
        </div>
        <h4 class="text-sm font-semibold">Kafolat xatlari</h4>
        <div class="table-container rounded-none border-0">
          <table class="table text-sm"><thead><tr><th>Raqam</th><th>Bemor</th><th>Polis</th><th>Sana</th><th class="text-right">Limit</th><th class="text-right">Ishlatilgan</th><th>Holat</th><th></th></tr></thead>
            <tbody><tr v-for="g in letters" :key="g.id" :data-testid="`letter-${g.number}`"><td class="font-mono">{{ g.number }}</td><td>{{ g.patient }}</td><td class="font-mono">{{ g.policy_number }}</td><td class="text-xs">{{ g.letter_date }}</td>
              <td class="text-right font-mono">{{ fmt(g.amount_limit) }}</td><td class="text-right font-mono">{{ fmt(g.used_amount) }}</td><td><span :class="letterClass[g.state]">{{ letterLabel[g.state] }}</span></td>
              <td class="whitespace-nowrap"><button v-if="g.has_file" class="text-xs text-cyan-600 hover:underline mr-2" @click="downloadLetter(g)">Skan</button>
                <label v-if="canWrite && g.state !== 'Cancelled'" class="text-xs text-cyan-600 hover:underline cursor-pointer mr-2">Fayl<input type="file" class="hidden" accept=".pdf,.jpg,.jpeg,.png" @change="uploadLetter(g, $event)" /></label>
                <button v-if="canWrite && g.state !== 'Cancelled'" class="text-xs text-red-500 hover:underline" @click="cancelLetter(g)">Bekor</button></td></tr>
              <tr v-if="!letters.length"><td colspan="8" class="text-center text-slate-400 py-4">Kafolat xati yo'q</td></tr></tbody></table>
        </div>
      </div>

      <!-- Qarzdorlik va reyestr -->
      <div v-else class="p-4 space-y-5" data-testid="ins-debts">
        <div class="table-container rounded-none border-0">
          <table class="table text-sm"><thead><tr><th>Kompaniya</th><th class="text-right">Hisoblangan</th><th class="text-right">To'langan</th><th class="text-right">Qarz</th><th class="text-right">Muddati o'tgan</th><th></th></tr></thead>
            <tbody><tr v-for="d in debts" :key="d.insurer_id" :data-testid="`debt-${d.insurer}`"><td class="font-medium">{{ d.insurer }}</td><td class="text-right font-mono">{{ fmt(d.charged) }}</td><td class="text-right font-mono">{{ fmt(d.paid) }}</td>
              <td class="text-right font-mono font-semibold" :class="d.balance > 0 ? 'text-amber-600' : ''">{{ fmt(d.balance) }}</td><td class="text-right font-mono text-red-600">{{ fmt(d.overdue) }}</td>
              <td class="whitespace-nowrap"><button class="text-xs text-cyan-600 hover:underline mr-2" @click="openDebt(d)">Batafsil</button>
                <button v-if="canManage" class="text-xs text-cyan-600 hover:underline" data-testid="ins-pay" @click="openPayment(d)">To'lov kiritish</button></td></tr>
              <tr v-if="!debts.length"><td colspan="6" class="text-center text-slate-400 py-4">Qarz yo'q</td></tr></tbody></table>
        </div>
        <div v-if="canManage" class="rounded-xl p-4 space-y-3" :class="dark ? 'bg-slate-800' : 'bg-slate-50'" data-testid="ins-registry">
          <h4 class="text-sm font-semibold">Oylik reyestr (Excel)</h4>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 items-end">
            <div class="col-span-2"><label class="lbl">Kompaniya</label><select v-model="reg.insurer_id" class="input" data-testid="reg-insurer"><option v-for="i in insurers" :key="i.id" :value="i.id">{{ i.name }}</option></select></div>
            <div><label class="lbl">Oy</label><input v-model="reg.month" type="month" class="input" data-testid="reg-month" /></div>
            <button class="btn-primary" :disabled="!reg.insurer_id" data-testid="reg-download" @click="downloadRegistry">Reyestrni yuklash</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Kompaniya -->
    <div v-if="modal === 'insurer'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-lg')"><h3 :class="titleClass">{{ insForm.id ? 'Kompaniyani tahrirlash' : 'Yangi kompaniya' }}</h3>
        <div class="grid grid-cols-2 gap-3">
          <div class="col-span-2"><label class="lbl">Nomi *</label><input v-model="insForm.name" class="input" data-testid="insurer-name" /></div>
          <div><label class="lbl">STIR</label><input v-model="insForm.tin" class="input" /></div><div><label class="lbl">To'lov muddati (kun)</label><input v-model.number="insForm.payment_days" type="number" min="0" class="input" /></div>
          <div><label class="lbl">Telefon</label><input v-model="insForm.phone" class="input" /></div><div><label class="lbl">Aloqa shaxsi</label><input v-model="insForm.contact_person" class="input" /></div>
          <label v-if="insForm.id" class="flex items-center gap-2 text-sm col-span-2"><input v-model="insForm.is_active" type="checkbox" /> Faol</label>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="insurer-save" @click="saveInsurer">Saqlash</button></div></div>
    </div>

    <!-- Shartnoma -->
    <div v-if="modal === 'contract'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-2xl')"><h3 :class="titleClass">{{ ctForm.id ? 'Shartnomani tahrirlash' : 'Yangi shartnoma' }}</h3>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="col-span-2"><label class="lbl">Kompaniya *</label><select v-model="ctForm.insurer_id" class="input" :disabled="!!ctForm.id" data-testid="ct-insurer"><option v-for="i in insurers" :key="i.id" :value="i.id">{{ i.name }}</option></select></div>
          <div class="col-span-2"><label class="lbl">Raqam *</label><input v-model="ctForm.number" class="input" data-testid="ct-number" /></div>
          <div><label class="lbl">Dan *</label><input v-model="ctForm.valid_from" type="date" class="input" data-testid="ct-from" /></div><div><label class="lbl">Gacha</label><input v-model="ctForm.valid_to" type="date" class="input" /></div>
          <div><label class="lbl">Chegirma %</label><input v-model.number="ctForm.discount_percent" type="number" min="0" max="100" step="0.01" class="input" data-testid="ct-discount" /></div>
          <div><label class="lbl">Yillik limit</label><input v-model.number="ctForm.annual_limit" type="number" min="0" class="input" placeholder="cheklovsiz" /></div>
          <div><label class="lbl">Bir hisob-faktura limiti</label><input v-model.number="ctForm.per_visit_limit" type="number" min="0" class="input" placeholder="cheklovsiz" /></div>
          <label class="flex items-center gap-2 text-sm col-span-2 pt-5"><input v-model="ctForm.requires_guarantee" type="checkbox" /> Kafolat xati talab qilinadi</label>
          <label class="flex items-center gap-2 text-sm col-span-2"><input v-model="ctForm.coverage_all" type="checkbox" data-testid="ct-all" /> Hamma xizmat qoplanadi</label>
          <div v-if="ctForm.coverage_all"><label class="lbl">Qoplash %</label><input v-model.number="ctForm.default_coverage_percent" type="number" min="1" max="100" class="input" /></div>
        </div>
        <div v-if="!ctForm.coverage_all" class="space-y-2">
          <p class="text-xs text-slate-400">Qoplanadigan xizmatlar</p>
          <div v-for="(l, i) in ctForm.services" :key="i" class="grid grid-cols-12 gap-2">
            <select v-model="l.service_id" class="input col-span-8" data-testid="ct-service"><option value="" disabled>Xizmat</option><option v-for="s in services" :key="s.id" :value="s.id">{{ s.name }}</option></select>
            <input v-model.number="l.coverage_percent" type="number" min="1" max="100" class="input col-span-3" data-testid="ct-percent" /><button class="text-red-500 col-span-1" @click="ctForm.services.splice(i, 1)">×</button></div>
          <button class="text-xs text-cyan-600" data-testid="ct-add-service" @click="ctForm.services.push({ service_id: '', coverage_percent: 100 })">+ Xizmat qo'shish</button>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="ct-save" @click="saveContract">Saqlash</button></div></div>
    </div>

    <!-- Polis -->
    <div v-if="modal === 'policy'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-lg')"><h3 :class="titleClass">Bemorga polis</h3>
        <div><label class="lbl">Bemor *</label><input v-model="pf.query" class="input" placeholder="Ism yoki telefon..." data-testid="pol-patient-search" @input="searchPatients" />
          <div v-if="patientHits.length && !pf.patient_id" class="border rounded-lg mt-1 max-h-32 overflow-y-auto"><button v-for="p in patientHits" :key="p.id" class="block w-full text-left px-3 py-1.5 text-sm hover:bg-slate-100" data-testid="pol-patient-hit" @click="pickPatient(p)">{{ p.name }} <span class="text-xs text-slate-400">{{ p.phone }}</span></button></div>
          <p v-if="pf.patient_id" class="text-xs text-emerald-600 mt-1">Tanlandi: {{ pf.query }}</p></div>
        <div class="grid grid-cols-2 gap-3">
          <div class="col-span-2"><label class="lbl">Shartnoma *</label><select v-model="pf.contract_id" class="input" data-testid="pol-contract"><option v-for="c in contracts" :key="c.id" :value="c.id">{{ c.insurer }}: {{ c.number }}</option></select></div>
          <div><label class="lbl">Polis raqami *</label><input v-model="pf.number" class="input" data-testid="pol-number" /></div><div></div>
          <div><label class="lbl">Dan *</label><input v-model="pf.valid_from" type="date" class="input" /></div><div><label class="lbl">Gacha</label><input v-model="pf.valid_to" type="date" class="input" /></div>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="pol-save" @click="savePolicy">Saqlash</button></div></div>
    </div>

    <!-- Kafolat xati -->
    <div v-if="modal === 'letter'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-lg')"><h3 :class="titleClass">Kafolat xati</h3>
        <div><label class="lbl">Polis *</label><select v-model="lf.policy_id" class="input" data-testid="let-policy"><option value="" disabled>Tanlang</option><option v-for="p in policies.filter(x => x.valid_now)" :key="p.id" :value="p.id">{{ p.patient }} · {{ p.number }}</option></select></div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="lbl">Raqam *</label><input v-model="lf.number" class="input" data-testid="let-number" /></div><div><label class="lbl">Sana *</label><input v-model="lf.letter_date" type="date" class="input" /></div>
          <div><label class="lbl">Summa limiti *</label><input v-model.number="lf.amount_limit" type="number" min="1" class="input" data-testid="let-limit" /></div><div></div>
          <div><label class="lbl">Muddat dan</label><input v-model="lf.valid_from" type="date" class="input" /></div><div><label class="lbl">gacha</label><input v-model="lf.valid_to" type="date" class="input" /></div>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="let-save" @click="saveLetter">Saqlash</button></div></div>
    </div>

    <!-- To'lov -->
    <div v-if="modal === 'payment'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-md')"><h3 :class="titleClass">{{ payForm.insurer }}: to'lov kiritish</h3>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="lbl">Summa *</label><input v-model.number="payForm.amount" type="number" min="1" step="0.01" class="input" data-testid="pay-amount" /></div>
          <div><label class="lbl">Sana</label><input v-model="payForm.paid_on" type="date" :max="today" class="input" /></div>
          <div class="col-span-2"><label class="lbl">Topshiriqnoma raqami</label><input v-model="payForm.reference" class="input" /></div>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="pay-save" @click="savePayment">Saqlash</button></div></div>
    </div>

    <!-- Qarz tafsiloti -->
    <div v-if="debtDetail" class="modal-overlay" @click.self="debtDetail = null">
      <div :class="boxClass('max-w-3xl')"><h3 :class="titleClass">{{ debtDetail.insurer }}: ochiq hisob-fakturalar</h3>
        <p class="text-xs text-slate-500">Muddat kesimi: o'tmagan {{ fmt(debtDetail.aging.current) }} · 1-30 kun {{ fmt(debtDetail.aging.d1_30) }} · 31-60 {{ fmt(debtDetail.aging.d31_60) }} · 61-90 {{ fmt(debtDetail.aging.d61_90) }} · 90+ {{ fmt(debtDetail.aging.d90_plus) }}</p>
        <div class="table-container rounded-none border-0"><table class="table text-sm"><thead><tr><th>Hisob-faktura</th><th>Sana</th><th>Bemor</th><th class="text-right">Ulush</th><th class="text-right">Qoldiq</th><th>Muddat</th></tr></thead>
          <tbody><tr v-for="r in debtDetail.open_invoices" :key="r.invoice_id"><td class="font-mono">{{ r.number }}</td><td>{{ r.date }}</td><td>{{ r.patient }}</td><td class="text-right font-mono">{{ fmt(r.amount) }}</td><td class="text-right font-mono">{{ fmt(r.outstanding) }}</td>
            <td :class="r.days_overdue ? 'text-red-600' : ''">{{ r.due_date }}<span v-if="r.days_overdue"> ({{ r.days_overdue }} kun kechikdi)</span></td></tr></tbody></table></div>
        <div class="flex justify-end"><button class="btn-secondary" @click="debtDetail = null">Yopish</button></div></div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast(), theme = useThemeStore(), auth = useAuthStore()
const dark = computed(() => theme.isDark)
const boxClass = w => ['w-full rounded-2xl shadow-2xl p-6 max-h-[92vh] overflow-y-auto space-y-4', w, dark.value ? 'bg-slate-900 border border-slate-800' : 'bg-white']
const titleClass = computed(() => ['font-heading font-semibold', dark.value ? 'text-white' : 'text-slate-900'])
const fmt = v => new Intl.NumberFormat('ru-RU').format(v ?? 0)
const today = new Date().toISOString().slice(0, 10)
const canManage = computed(() => auth.can('insurance:manage')), canWrite = computed(() => auth.can('insurance:write'))
const tabs = computed(() => [{ key: 'insurers', label: 'Kompaniyalar va shartnomalar' }, { key: 'policies', label: 'Polislar va kafolat xatlari' }, { key: 'debts', label: 'Qarzdorlik va reyestr' }])
const letterLabel = { Active: 'Faol', Expired: "Muddati o'tgan", Exhausted: 'Limit tugagan', Cancelled: 'Bekor qilingan' }
const letterClass = { Active: 'badge-green', Expired: 'badge-yellow', Exhausted: 'badge-yellow', Cancelled: 'badge-slate' }

const tab = ref('insurers'), modal = ref(''), busy = ref(false)
const insurers = ref([]), contracts = ref([]), services = ref([]), policies = ref([]), letters = ref([]), debts = ref([]), debtDetail = ref(null)
const policySearch = ref('')
const contractsOf = id => contracts.value.filter(c => c.insurer_id === id)

async function loadCatalog() {
  try {
    insurers.value = (await api.get('/insurance/insurers')).data
    contracts.value = (await api.get('/insurance/contracts')).data
    if (auth.can('services:read')) services.value = (await api.get('/services')).data
  } catch (e) { toast.error(e, "Sug'urta katalogini yuklab bo'lmadi") }
}
async function loadPolicies() {
  try {
    policies.value = (await api.get('/insurance/policies', { params: policySearch.value ? { number: policySearch.value } : {} })).data
    letters.value = (await api.get('/insurance/guarantee-letters')).data
  } catch (e) { toast.error(e, "Polislarni yuklab bo'lmadi") }
}
async function loadDebts() { try { debts.value = (await api.get('/insurance/debts')).data } catch (e) { toast.error(e, "Qarzdorlikni yuklab bo'lmadi") } }
watch(tab, t => { if (t === 'policies') loadPolicies(); if (t === 'debts') loadDebts() })

// Kompaniya
const insForm = reactive({ id: null, name: '', tin: '', phone: '', contact_person: '', payment_days: 30, is_active: true })
function openInsurer(i) { Object.assign(insForm, i ? { id: i.id, name: i.name, tin: i.tin || '', phone: i.phone || '', contact_person: i.contact_person || '', payment_days: i.payment_days, is_active: i.is_active } : { id: null, name: '', tin: '', phone: '', contact_person: '', payment_days: 30, is_active: true }); modal.value = 'insurer' }
async function saveInsurer() {
  busy.value = true
  const body = { name: insForm.name, tin: insForm.tin || null, phone: insForm.phone || null, contact_person: insForm.contact_person || null, payment_days: insForm.payment_days }
  try { if (insForm.id) await api.put(`/insurance/insurers/${insForm.id}`, { ...body, is_active: insForm.is_active }); else await api.post('/insurance/insurers', body); toast.success('Kompaniya saqlandi'); modal.value = ''; await loadCatalog() }
  catch (e) { toast.error(e, "Kompaniyani saqlab bo'lmadi") } finally { busy.value = false }
}

// Shartnoma
const blankCt = () => ({ id: null, insurer_id: '', number: '', valid_from: today, valid_to: '', discount_percent: 0, annual_limit: null, per_visit_limit: null, requires_guarantee: false, coverage_all: false, default_coverage_percent: 100, services: [] })
const ctForm = reactive(blankCt())
function openContract(c) {
  Object.assign(ctForm, c ? { id: c.id, insurer_id: c.insurer_id, number: c.number, valid_from: c.valid_from, valid_to: c.valid_to || '', discount_percent: c.discount_percent, annual_limit: c.annual_limit, per_visit_limit: c.per_visit_limit,
    requires_guarantee: c.requires_guarantee, coverage_all: c.coverage_all, default_coverage_percent: c.default_coverage_percent, services: c.services.map(s => ({ service_id: s.service_id, coverage_percent: s.coverage_percent })) } : { ...blankCt(), insurer_id: insurers.value[0]?.id || '' })
  modal.value = 'contract'
}
async function saveContract() {
  busy.value = true
  const body = { number: ctForm.number, valid_from: ctForm.valid_from, valid_to: ctForm.valid_to || null, discount_percent: ctForm.discount_percent || 0, annual_limit: ctForm.annual_limit || null, per_visit_limit: ctForm.per_visit_limit || null,
    requires_guarantee: ctForm.requires_guarantee, coverage_all: ctForm.coverage_all, default_coverage_percent: ctForm.default_coverage_percent || 100,
    services: ctForm.coverage_all ? [] : ctForm.services.filter(s => s.service_id).map(s => ({ service_id: s.service_id, coverage_percent: s.coverage_percent || 100 })) }
  try {
    if (ctForm.id) await api.put(`/insurance/contracts/${ctForm.id}`, body); else await api.post('/insurance/contracts', { ...body, insurer_id: ctForm.insurer_id })
    toast.success('Shartnoma saqlandi'); modal.value = ''; await loadCatalog()
  } catch (e) { toast.error(e, "Shartnomani saqlab bo'lmadi") } finally { busy.value = false }
}

// Polis
const pf = reactive({ query: '', patient_id: '', contract_id: '', number: '', valid_from: today, valid_to: '' }), patientHits = ref([])
async function searchPatients() {
  pf.patient_id = ''
  if (pf.query.trim().length < 2) { patientHits.value = []; return }
  try { patientHits.value = (await api.get('/patients', { params: { search: pf.query, limit: 8 } })).data } catch { patientHits.value = [] }
}
function pickPatient(p) { pf.patient_id = p.id; pf.query = p.name; patientHits.value = [] }
function openPolicy() { Object.assign(pf, { query: '', patient_id: '', contract_id: contracts.value[0]?.id || '', number: '', valid_from: today, valid_to: '' }); patientHits.value = []; modal.value = 'policy' }
async function savePolicy() {
  busy.value = true
  try {
    await api.post(`/patients/${pf.patient_id}/policies`, { contract_id: pf.contract_id, number: pf.number, valid_from: pf.valid_from, valid_to: pf.valid_to || null })
    toast.success('Polis saqlandi'); modal.value = ''; await loadPolicies()
  } catch (e) { toast.error(e, "Polisni saqlab bo'lmadi") } finally { busy.value = false }
}

// Kafolat xati
const lf = reactive({ policy_id: '', number: '', letter_date: today, amount_limit: null, valid_from: '', valid_to: '' })
function openLetter() { Object.assign(lf, { policy_id: '', number: '', letter_date: today, amount_limit: null, valid_from: '', valid_to: '' }); modal.value = 'letter' }
async function saveLetter() {
  busy.value = true
  try {
    await api.post('/insurance/guarantee-letters', { policy_id: lf.policy_id, number: lf.number, letter_date: lf.letter_date, amount_limit: lf.amount_limit, valid_from: lf.valid_from || null, valid_to: lf.valid_to || null })
    toast.success('Kafolat xati saqlandi'); modal.value = ''; await loadPolicies()
  } catch (e) { toast.error(e, "Kafolat xatini saqlab bo'lmadi") } finally { busy.value = false }
}
async function uploadLetter(g, ev) {
  const file = ev.target.files[0]
  if (!file) return
  const form = new FormData(); form.append('file', file)
  try { await api.post(`/insurance/guarantee-letters/${g.id}/file`, form, { headers: { 'Content-Type': 'multipart/form-data' } }); toast.success('Fayl biriktirildi'); await loadPolicies() } catch (e) { toast.error(e, "Faylni yuklab bo'lmadi") }
}
async function downloadLetter(g) {
  try { const { data } = await api.get(`/insurance/guarantee-letters/${g.id}/file`, { responseType: 'blob' }); window.open(URL.createObjectURL(data), '_blank') } catch (e) { toast.error(e, "Faylni ochib bo'lmadi") }
}
async function cancelLetter(g) {
  const reason = window.prompt('Bekor qilish sababi:')
  if (!reason || reason.trim().length < 3) return
  try { await api.post(`/insurance/guarantee-letters/${g.id}/cancel`, { reason }); toast.success('Kafolat xati bekor qilindi'); await loadPolicies() } catch (e) { toast.error(e, "Bekor qilib bo'lmadi") }
}

// Qarz, to'lov, reyestr
const payForm = reactive({ insurer_id: '', insurer: '', amount: null, paid_on: today, reference: '' })
function openPayment(d) { Object.assign(payForm, { insurer_id: d.insurer_id, insurer: d.insurer, amount: null, paid_on: today, reference: '' }); modal.value = 'payment' }
async function savePayment() {
  busy.value = true
  try { await api.post('/insurance/payments', { insurer_id: payForm.insurer_id, amount: payForm.amount, paid_on: payForm.paid_on || null, reference: payForm.reference || null }); toast.success("To'lov yozildi"); modal.value = ''; await loadDebts() }
  catch (e) { toast.error(e, "To'lovni yozib bo'lmadi") } finally { busy.value = false }
}
async function openDebt(d) { try { debtDetail.value = (await api.get(`/insurance/debts/${d.insurer_id}`)).data } catch (e) { toast.error(e, "Qarz tafsilotini yuklab bo'lmadi") } }
const reg = reactive({ insurer_id: '', month: today.slice(0, 7) })
async function downloadRegistry() {
  try {
    const { data } = await api.get('/insurance/registry', { params: { insurer_id: reg.insurer_id, month: reg.month, format: 'xlsx' }, responseType: 'blob' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(data); a.download = `reyestr_${reg.month}.xlsx`; document.body.appendChild(a); a.click(); a.remove()
  } catch (e) { toast.error(e, "Reyestrni yuklab bo'lmadi") }
}
onMounted(async () => { await loadCatalog(); reg.insurer_id = insurers.value[0]?.id || '' })
</script>

<style scoped>
.lbl { display: block; font-size: 0.75rem; color: rgb(148 163 184); margin-bottom: 0.25rem; }
</style>
