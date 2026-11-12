<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Shifokor foizi</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">To'lov kelganda hisoblanadi, qaytarishda proporsional qaytariladi</p>
      </div>
      <input v-model="month" type="month" class="input w-auto" @change="load" />
    </div>

    <div class="card">
      <p v-if="loading" class="p-8 text-center text-sm text-slate-400">Yuklanmoqda...</p>
      <EmptyState v-else-if="error" title="Hisobotni yuklab bo'lmadi" action-label="Qayta urinish" @action="load" />
      <EmptyState v-else-if="!report.doctors.length" title="Bu oyda foiz yozuvi yo'q" description="To'lovlar va qoidalar bo'lsa yozuvlar shu yerda paydo bo'ladi" />
      <div v-else class="table-container rounded-none border-0">
        <table class="table">
          <thead><tr><th>Shifokor</th><th class="text-right">Hisoblangan</th><th class="text-right">Qaytarilgan</th><th class="text-right">Sof</th><th>Yozuvlar</th><th>Holat</th><th></th></tr></thead>
          <tbody>
            <template v-for="d in report.doctors" :key="d.doctor_id">
              <tr>
                <td class="font-medium">{{ d.doctor }}</td>
                <td class="text-right font-mono">{{ fmt(d.accrued) }}</td>
                <td class="text-right font-mono text-red-500">{{ fmt(d.reversed) }}</td>
                <td class="text-right font-mono font-semibold">{{ fmt(d.net) }}</td>
                <td><button class="text-xs text-cyan-600 hover:underline" @click="toggle(d)">{{ d.entries }} ta</button></td>
                <td><span :class="d.settled ? 'badge-green' : 'badge-yellow'">{{ d.settled ? 'Yopilgan' : 'Ochiq' }}</span></td>
                <td><button v-if="canManage && !d.settled" class="text-xs text-cyan-600 underline" :disabled="busy" @click="settle(d)">Oyni yopish</button></td>
              </tr>
              <tr v-if="open === d.doctor_id"><td colspan="7" :class="dark ? 'bg-slate-800/40' : 'bg-slate-50'">
                <table class="w-full text-xs">
                  <tr v-for="e in entries" :key="e.id" class="border-t" :class="dark ? 'border-slate-800' : 'border-slate-200'">
                    <td class="py-1 font-mono">{{ e.entry_date }}</td><td>{{ e.invoice_number }}</td><td>{{ e.service }}</td>
                    <td>{{ e.rule_kind === 'Percent' ? e.rule_percent + '%' : fmt(e.rule_fixed) + ' (fiks)' }}</td>
                    <td class="text-right font-mono">{{ fmt(e.base_amount) }}</td>
                    <td class="text-right font-mono" :class="e.amount < 0 ? 'text-red-500' : ''">{{ fmt(e.amount) }}</td>
                    <td>{{ e.kind === 'Reversal' ? 'qaytarish' : '' }}</td>
                  </tr>
                </table>
              </td></tr>
            </template>
          </tbody>
        </table>
      </div>
      <p v-if="report.doctors.length" class="p-4 text-sm text-right">Jami sof: <b class="font-mono">{{ fmt(report.total_net) }}</b> UZS</p>
    </div>

    <div v-if="canManage" class="card p-5 space-y-4">
      <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Qoidalar</h3>
      <p class="text-xs text-slate-400">Tanlash: shifokor+xizmat &gt; shifokor &gt; xizmat &gt; umumiy; teng bo'lsa boshlanishi kechroq qoida. Asos: to'langan summa (chegirmadan keyin).</p>
      <form class="grid grid-cols-2 sm:grid-cols-8 gap-2 items-end" @submit.prevent="addRule">
        <div class="sm:col-span-2"><label class="text-xs text-slate-400 block mb-1">Shifokor</label><select v-model="rule.doctor_id" class="input"><option value="">Hamma</option><option v-for="d in doctors" :key="d.id" :value="d.id">{{ d.name }}</option></select></div>
        <div class="sm:col-span-2"><label class="text-xs text-slate-400 block mb-1">Xizmat</label><select v-model="rule.service_id" class="input"><option value="">Hamma</option><option v-for="s in services" :key="s.id" :value="s.id">{{ s.name }}</option></select></div>
        <div><label class="text-xs text-slate-400 block mb-1">Turi</label><select v-model="rule.kind" class="input"><option value="Percent">Foiz</option><option value="Fixed">Summa</option></select></div>
        <div><label class="text-xs text-slate-400 block mb-1">{{ rule.kind === 'Percent' ? '%' : 'UZS / birlik' }}</label><input v-model.number="rule.value" type="number" min="0.01" step="0.01" class="input" required /></div>
        <div><label class="text-xs text-slate-400 block mb-1">Dan</label><input v-model="rule.valid_from" type="date" class="input" required /></div>
        <div><label class="text-xs text-slate-400 block mb-1">Gacha</label><input v-model="rule.valid_to" type="date" class="input" /></div>
        <div><label class="text-xs text-slate-400 block mb-1">Asos</label><select v-model="rule.base" class="input"><option value="WithVat">QQS bilan</option><option value="NetOfVat">QQSsiz</option></select></div>
        <button class="btn-primary text-sm" :disabled="busy"><Plus class="w-4 h-4" /> Qo'shish</button>
      </form>
      <EmptyState v-if="!rules.length" title="Qoida yo'q" />
      <ul v-else class="divide-y" :class="dark ? 'divide-slate-800' : 'divide-slate-100'">
        <li v-for="r in rules" :key="r.id" class="py-2 flex items-center gap-3 text-sm flex-wrap">
          <span class="font-medium">{{ r.doctor || 'Hamma shifokor' }}</span><span class="text-slate-400">·</span><span>{{ r.service || 'hamma xizmat' }}</span>
          <span class="badge-blue">{{ r.kind === 'Percent' ? r.percent + '%' : fmt(r.fixed_amount) + ' UZS' }}</span>
          <span class="text-xs text-slate-400">{{ r.valid_from }} – {{ r.valid_to || '…' }} · {{ r.base === 'WithVat' ? 'QQS bilan' : 'QQSsiz' }}</span>
          <span class="flex-1"></span>
          <button class="text-xs text-red-500 underline" @click="deactivate(r)">O'chirib qo'yish</button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast()
const theme = useThemeStore()
const auth = useAuthStore()
const dark = computed(() => theme.isDark)
const canManage = computed(() => auth.can('commissions:manage'))
const fmt = v => new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 2 }).format(v ?? 0)

const month = ref(new Date().toISOString().slice(0, 7))
const report = ref({ doctors: [], total_net: 0 }), loading = ref(true), error = ref(false), busy = ref(false)
const open = ref(null), entries = ref([])
async function load() {
  loading.value = true; error.value = false; open.value = null
  try { report.value = (await api.get('/commissions/report', { params: { month: month.value } })).data } catch (e) {
    report.value = { doctors: [], total_net: 0 }; error.value = true; toast.error(e, "Hisobotni yuklab bo'lmadi")
  } finally { loading.value = false }
}
async function toggle(d) {
  if (open.value === d.doctor_id) { open.value = null; return }
  try { entries.value = (await api.get('/commissions/entries', { params: { month: month.value, doctor_id: d.doctor_id } })).data; open.value = d.doctor_id }
  catch (e) { toast.error(e, "Yozuvlarni yuklab bo'lmadi") }
}
async function settle(d) {
  busy.value = true
  try { await api.post('/commissions/settle', { month: month.value, doctor_id: d.doctor_id }); toast.success('Oy yopildi'); await load() }
  catch (e) { toast.error(e, "Oyni yopib bo'lmadi") } finally { busy.value = false }
}

// Qoidalar
const rules = ref([]), doctors = ref([]), services = ref([])
const blank = () => ({ doctor_id: '', service_id: '', kind: 'Percent', value: null, valid_from: new Date().toISOString().slice(0, 10), valid_to: '', base: 'WithVat' })
const rule = reactive(blank())
async function loadRules() { try { rules.value = (await api.get('/commission-rules')).data } catch (e) { rules.value = []; toast.error(e, "Qoidalarni yuklab bo'lmadi") } }
async function addRule() {
  busy.value = true
  const body = { doctor_id: rule.doctor_id || null, service_id: rule.service_id || null, kind: rule.kind, base: rule.base, valid_from: rule.valid_from, valid_to: rule.valid_to || null,
                 percent: rule.kind === 'Percent' ? rule.value : null, fixed_amount: rule.kind === 'Fixed' ? rule.value : null }
  try { await api.post('/commission-rules', body); toast.success("Qoida qo'shildi"); Object.assign(rule, blank()); await loadRules() }
  catch (e) { toast.error(e, "Qoidani qo'shib bo'lmadi") } finally { busy.value = false }
}
async function deactivate(r) {
  try {
    await api.put(`/commission-rules/${r.id}`, { doctor_id: r.doctor_id, service_id: r.service_id, kind: r.kind, percent: r.percent, fixed_amount: r.fixed_amount,
      base: r.base, valid_from: r.valid_from, valid_to: r.valid_to, is_active: false })
    toast.success("Qoida o'chirib qo'yildi"); await loadRules()
  } catch (e) { toast.error(e, "Qoidani o'zgartirib bo'lmadi") }
}

onMounted(async () => {
  load()
  if (canManage.value) {
    loadRules()
    try { doctors.value = (await api.get('/staff', { params: { role: 'Doctor' } })).data } catch { doctors.value = [] }
    try { services.value = (await api.get('/services')).data } catch { services.value = [] }
  }
})
</script>
