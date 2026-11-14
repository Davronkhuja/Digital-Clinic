<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Ombor</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Dori va sarf materiallari, partiyalar, yaroqlilik muddati (FEFO) va filiallar orasida ko'chirish</p>
      </div>
      <div class="flex gap-2 flex-wrap">
        <button v-if="auth.can('warehouse:write')" class="btn-secondary" data-testid="wh-new-item" @click="openItem()"><Plus class="w-4 h-4" /> Material</button>
        <button v-if="auth.can('warehouse:write')" class="btn-primary" data-testid="wh-new-receipt" @click="openReceipt"><PackagePlus class="w-4 h-4" /> Kirim</button>
        <button v-if="auth.can('warehouse:write')" class="btn-secondary" data-testid="wh-new-issue" @click="openIssue"><PackageMinus class="w-4 h-4" /> Chiqim</button>
        <button v-if="auth.can('warehouse:transfer')" class="btn-secondary" data-testid="wh-new-transfer" @click="openTransfer"><Truck class="w-4 h-4" /> Ko'chirish</button>
      </div>
    </div>

    <!-- Ogohlantirishlar -->
    <div v-if="alertCount" class="grid gap-3 md:grid-cols-2 xl:grid-cols-4" data-testid="wh-alerts">
      <button v-if="alerts.low_stock.length" class="card p-4 text-left border-l-4 border-amber-400" @click="tab = 'stock'; lowOnly = true">
        <p class="text-xs text-slate-400">Minimal qoldiqdan kam</p><p class="text-2xl font-bold text-amber-600">{{ alerts.low_stock.length }}</p>
        <p class="text-xs text-slate-500 truncate">{{ alerts.low_stock.slice(0, 3).map(r => r.name).join(', ') }}</p>
      </button>
      <button v-if="alerts.expiring.length" class="card p-4 text-left border-l-4 border-orange-400" @click="tab = 'batches'; expOnly = true">
        <p class="text-xs text-slate-400">{{ alerts.expiry_days }} kunda muddati tugaydi</p><p class="text-2xl font-bold text-orange-600">{{ alerts.expiring.length }}</p>
        <p class="text-xs text-slate-500 truncate">{{ alerts.expiring.slice(0, 3).map(b => `${b.item} (${b.days_left} kun)`).join(', ') }}</p>
      </button>
      <button v-if="alerts.expired.length" class="card p-4 text-left border-l-4 border-red-500" @click="tab = 'batches'; expOnly = true">
        <p class="text-xs text-slate-400">Muddati o'tgan (hisobdan chiqaring)</p><p class="text-2xl font-bold text-red-600">{{ alerts.expired.length }}</p>
        <p class="text-xs text-slate-500 truncate">{{ alerts.expired.slice(0, 3).map(b => b.item).join(', ') }}</p>
      </button>
      <button v-if="alerts.shortages.length" class="card p-4 text-left border-l-4 border-rose-400" @click="tab = 'shortages'">
        <p class="text-xs text-slate-400">To'lovda yetmagan sarf</p><p class="text-2xl font-bold text-rose-600">{{ alerts.shortages.length }}</p>
        <p class="text-xs text-slate-500 truncate">{{ alerts.shortages.slice(0, 3).map(s => s.item).join(', ') }}</p>
      </button>
    </div>

    <div class="card">
      <div :class="['px-4 pt-3 border-b flex gap-1 flex-wrap', dark ? 'border-slate-800' : 'border-slate-100']" role="tablist">
        <button v-for="t in tabs" :key="t.key" role="tab" :aria-selected="tab === t.key" :data-testid="`wh-tab-${t.key}`"
          :class="['px-3 py-2 text-sm rounded-t-lg', tab === t.key ? 'border-b-2 border-cyan-500 font-semibold text-cyan-600' : 'text-slate-500']" @click="tab = t.key">{{ t.label }}</button>
      </div>
      <p v-if="loading" class="p-8 text-center text-sm text-slate-400">Yuklanmoqda...</p>
      <EmptyState v-else-if="error" title="Yuklab bo'lmadi" action-label="Qayta urinish" @action="loadTab" />

      <!-- Qoldiq -->
      <div v-else-if="tab === 'stock'" data-testid="wh-stock">
        <div class="p-4 flex gap-3 flex-wrap">
          <input v-model="search" class="input flex-1 min-w-48" placeholder="Nom yoki SKU..." @input="loadTab" />
          <label class="flex items-center gap-2 text-sm"><input v-model="lowOnly" type="checkbox" /> Faqat minimaldan kam</label>
        </div>
        <EmptyState v-if="!shownStock.length" title="Material yo'q" description="Avval material qo'shing, keyin kirim qiling" />
        <div v-else class="table-container rounded-none border-0">
          <table class="table"><thead><tr><th>Material</th><th>Turi</th><th class="text-right">Qoldiq</th><th class="text-right">Yaroqli</th><th class="text-right">Min.</th><th class="text-right">Qiymat (UZS)</th><th></th></tr></thead>
            <tbody>
              <tr v-for="r in shownStock" :key="r.item_id">
                <td class="font-medium">{{ r.name }} <span v-if="r.sku" class="text-xs text-slate-400 font-mono">{{ r.sku }}</span></td>
                <td class="text-sm text-slate-500">{{ r.kind === 'Medicine' ? 'Dori' : 'Sarf' }}</td>
                <td class="text-right font-mono">{{ q(r.qty) }} <span class="text-xs text-slate-400">{{ r.unit }}</span></td>
                <td class="text-right font-mono" :class="r.low ? 'text-amber-600 font-semibold' : ''">{{ q(r.usable_qty) }}</td>
                <td class="text-right font-mono text-slate-500">{{ q(r.min_qty) }}</td>
                <td class="text-right font-mono">{{ fmt(r.value) }}</td>
                <td class="whitespace-nowrap">
                  <span v-if="r.low" class="badge-yellow mr-2">Kam</span><span v-if="r.expired_qty > 0" class="badge-red mr-2">Muddati o'tgan {{ q(r.expired_qty) }}</span>
                  <button v-if="auth.can('warehouse:write')" class="text-xs text-cyan-600 hover:underline" @click="openItem(r)">Tahrirlash</button>
                </td>
              </tr>
            </tbody></table>
        </div>
      </div>

      <!-- Partiyalar -->
      <div v-else-if="tab === 'batches'" data-testid="wh-batches">
        <div class="p-4"><label class="flex items-center gap-2 text-sm"><input v-model="expOnly" type="checkbox" /> Faqat muddati yaqin yoki o'tgan ({{ alerts.expiry_days }} kun)</label></div>
        <EmptyState v-if="!shownBatches.length" title="Partiya yo'q" />
        <div v-else class="table-container rounded-none border-0">
          <table class="table"><thead><tr><th>Material</th><th>Partiya</th><th>Muddati</th><th class="text-right">Qoldiq</th><th class="text-right">Narx</th><th></th></tr></thead>
            <tbody>
              <tr v-for="b in shownBatches" :key="b.id">
                <td class="font-medium">{{ b.item }}</td><td class="font-mono text-sm">{{ b.batch_no }}</td>
                <td class="text-sm"><span :class="b.expired ? 'text-red-600 font-semibold' : b.days_left != null && b.days_left <= alerts.expiry_days ? 'text-orange-600' : ''">{{ b.expires_on || 'muddatsiz' }}</span>
                  <span v-if="b.days_left != null" class="text-xs text-slate-400 ml-1">({{ b.expired ? 'o\'tgan' : b.days_left + ' kun' }})</span></td>
                <td class="text-right font-mono">{{ q(b.qty_remaining) }} <span class="text-xs text-slate-400">{{ b.unit }}</span></td>
                <td class="text-right font-mono">{{ fmt(b.unit_cost) }}</td>
                <td><button v-if="auth.can('warehouse:write')" class="text-xs text-red-500 hover:underline" data-testid="wh-writeoff" @click="openWriteoff(b)">Hisobdan chiqarish</button></td>
              </tr>
            </tbody></table>
        </div>
      </div>

      <!-- Kirim hujjatlari -->
      <div v-else-if="tab === 'receipts'" data-testid="wh-receipts">
        <EmptyState v-if="!receipts.length" title="Kirim yo'q" description="Birinchi kirim hujjatini yarating" />
        <div v-else class="divide-y" :class="dark ? 'divide-slate-800' : 'divide-slate-100'">
          <div v-for="r in receipts" :key="r.id" class="p-4 space-y-1">
            <div class="flex justify-between gap-2 flex-wrap"><p class="font-semibold">{{ r.received_on }} · {{ r.supplier || 'Yetkazib beruvchi ko\'rsatilmagan' }} <span v-if="r.doc_no" class="text-xs text-slate-400">№ {{ r.doc_no }}</span></p><p class="font-mono">{{ fmt(r.total) }} UZS</p></div>
            <p v-for="(l, i) in r.lines" :key="i" class="text-xs text-slate-500">{{ l.item }}: {{ q(l.qty) }} {{ l.unit }} × {{ fmt(l.unit_cost) }} · partiya {{ l.batch_no }} · {{ l.expires_on || 'muddatsiz' }}</p>
          </div>
        </div>
      </div>

      <!-- Harakatlar -->
      <div v-else-if="tab === 'movements'" data-testid="wh-movements">
        <EmptyState v-if="!movements.length" title="Harakat yo'q" />
        <div v-else class="table-container rounded-none border-0">
          <table class="table"><thead><tr><th>Vaqt</th><th>Tur</th><th>Material</th><th>Partiya</th><th class="text-right">Miqdor</th><th>Sabab</th><th>Kim</th></tr></thead>
            <tbody><tr v-for="m in movements" :key="m.id">
              <td class="font-mono text-xs">{{ m.at.slice(0, 16).replace('T', ' ') }}</td><td><span class="badge-slate">{{ kindLabel[m.kind] || m.kind }}</span></td>
              <td>{{ m.item }}</td><td class="font-mono text-xs">{{ m.batch_no }}</td>
              <td class="text-right font-mono" :class="m.qty < 0 ? 'text-red-600' : 'text-emerald-600'">{{ m.qty > 0 ? '+' : '' }}{{ q(m.qty) }} {{ m.unit }}</td>
              <td class="text-xs text-slate-500">{{ m.reason }}</td><td class="text-xs text-slate-500">{{ m.by }}</td></tr></tbody></table>
        </div>
      </div>

      <!-- Ko'chirish -->
      <div v-else-if="tab === 'transfers'" data-testid="wh-transfers">
        <EmptyState v-if="!transfers.length" title="Ko'chirish hujjati yo'q" />
        <div v-else class="divide-y" :class="dark ? 'divide-slate-800' : 'divide-slate-100'">
          <div v-for="t in transfers" :key="t.id" class="p-4 space-y-1">
            <div class="flex justify-between gap-2 flex-wrap items-center">
              <p class="font-semibold">{{ t.number }} · {{ t.from_branch }} → {{ t.to_branch }} <span :class="statusClass[t.status]">{{ statusLabel[t.status] }}</span></p>
              <span class="flex gap-3">
                <button v-if="t.status === 'Sent' && t.to_branch_id === currentBranch && auth.can('warehouse:transfer')" class="btn-primary text-sm" data-testid="wh-receive" @click="receiveTransfer(t)">Qabul qilish</button>
                <button v-if="t.status === 'Sent' && t.from_branch_id === currentBranch && auth.can('warehouse:transfer')" class="text-sm text-red-500 hover:underline" @click="cancelTransfer(t)">Bekor qilish</button>
              </span>
            </div>
            <p v-for="(l, i) in t.lines" :key="i" class="text-xs text-slate-500">{{ l.item }}: {{ q(l.qty) }} {{ l.unit }} · partiya {{ l.batch_no }} · {{ l.expires_on || 'muddatsiz' }}</p>
            <p v-if="t.cancel_reason" class="text-xs text-slate-400">Bekor qilish sababi: {{ t.cancel_reason }}</p>
          </div>
        </div>
      </div>

      <!-- Yetishmovchilik -->
      <div v-else-if="tab === 'shortages'" data-testid="wh-shortages">
        <EmptyState v-if="!alerts.shortages.length" title="Yetishmovchilik yo'q" />
        <div v-else class="table-container rounded-none border-0">
          <table class="table"><thead><tr><th>Hisob-faktura</th><th>Material</th><th class="text-right">Yetmagan</th><th></th></tr></thead>
            <tbody><tr v-for="s in alerts.shortages" :key="s.id"><td class="font-mono">{{ s.invoice_number }}</td><td>{{ s.item }}</td><td class="text-right font-mono">{{ q(s.qty_missing) }} {{ s.unit }}</td>
              <td><button v-if="auth.can('warehouse:write')" class="text-xs text-cyan-600 hover:underline" @click="resolveShortage(s)">Ombordan yozish</button></td></tr></tbody></table>
        </div>
      </div>
    </div>

    <!-- Material -->
    <div v-if="modal === 'item'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-lg')">
        <h3 :class="titleClass">{{ itemForm.id ? 'Materialni tahrirlash' : 'Yangi material' }}</h3>
        <div class="grid grid-cols-2 gap-3">
          <div class="col-span-2"><label class="lbl">Nomi *</label><input v-model="itemForm.name" class="input" placeholder="Shprits 5 ml" data-testid="item-name" /></div>
          <div><label class="lbl">Turi</label><select v-model="itemForm.kind" class="input"><option value="Supply">Sarf materiali</option><option value="Medicine">Dori</option></select></div>
          <div><label class="lbl">Birlik *</label><input v-model="itemForm.unit" class="input" placeholder="dona, ml, g" data-testid="item-unit" /></div>
          <div><label class="lbl">SKU</label><input v-model="itemForm.sku" class="input" /></div>
          <div><label class="lbl">Minimal qoldiq</label><input v-model.number="itemForm.min_qty" type="number" min="0" step="0.001" class="input" data-testid="item-min" /></div>
          <label v-if="itemForm.id" class="flex items-center gap-2 text-sm col-span-2"><input v-model="itemForm.is_active" type="checkbox" /> Faol</label>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="item-save" @click="saveItem">Saqlash</button></div>
      </div>
    </div>

    <!-- Kirim -->
    <div v-if="modal === 'receipt'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-3xl')">
        <h3 :class="titleClass">Kirim hujjati</h3>
        <div class="grid grid-cols-3 gap-3">
          <div><label class="lbl">Yetkazib beruvchi</label><input v-model="rcp.supplier" class="input" /></div>
          <div><label class="lbl">Hujjat raqami</label><input v-model="rcp.doc_no" class="input" /></div>
          <div><label class="lbl">Sana</label><input v-model="rcp.received_on" type="date" :max="today" class="input" /></div>
        </div>
        <div class="space-y-2">
          <div v-for="(l, i) in rcp.lines" :key="i" class="grid grid-cols-12 gap-2 items-end">
            <div class="col-span-3"><label v-if="i === 0" class="lbl">Material</label><select v-model="l.item_id" class="input" data-testid="rcp-item"><option value="" disabled>Tanlang</option><option v-for="it in items" :key="it.id" :value="it.id">{{ it.name }} ({{ it.unit }})</option></select></div>
            <div class="col-span-2"><label v-if="i === 0" class="lbl">Partiya №</label><input v-model="l.batch_no" class="input" data-testid="rcp-batch" /></div>
            <div class="col-span-2"><label v-if="i === 0" class="lbl">Muddati</label><input v-model="l.expires_on" type="date" :min="today" class="input" /></div>
            <div class="col-span-2"><label v-if="i === 0" class="lbl">Miqdor</label><input v-model.number="l.qty" type="number" min="0" step="0.001" class="input" data-testid="rcp-qty" /></div>
            <div class="col-span-2"><label v-if="i === 0" class="lbl">Narx (bir birlik)</label><input v-model.number="l.unit_cost" type="number" min="0" step="0.01" class="input" data-testid="rcp-cost" /></div>
            <button class="text-red-500 col-span-1 pb-2" :disabled="rcp.lines.length === 1" @click="rcp.lines.splice(i, 1)"><Trash2 class="w-4 h-4" /></button>
          </div>
          <button class="text-xs text-cyan-600" @click="rcp.lines.push(emptyLine())"><Plus class="w-3.5 h-3.5 inline" /> Qator qo'shish</button>
        </div>
        <p class="text-xs text-slate-400">Muddatsiz mahsulot uchun "Muddati" bo'sh qoldiriladi. Muddati o'tgan tovar qabul qilinmaydi.</p>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="rcp-save" @click="saveReceipt">Kirim qilish</button></div>
      </div>
    </div>

    <!-- Chiqim -->
    <div v-if="modal === 'issue'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-md')">
        <h3 :class="titleClass">Chiqim (FEFO: birinchi tugaydigan birinchi chiqadi)</h3>
        <div><label class="lbl">Material</label><select v-model="iss.item_id" class="input" data-testid="iss-item"><option value="" disabled>Tanlang</option><option v-for="it in items" :key="it.id" :value="it.id">{{ it.name }} ({{ it.unit }})</option></select></div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="lbl">Miqdor</label><input v-model.number="iss.qty" type="number" min="0" step="0.001" class="input" data-testid="iss-qty" /></div>
          <div><label class="lbl">Sabab / kimga</label><input v-model="iss.reason" class="input" placeholder="3-kabinet" data-testid="iss-reason" /></div>
        </div>
        <div v-if="issResult" class="rounded-xl bg-emerald-50 text-emerald-800 text-sm p-3 space-y-0.5" data-testid="iss-result">
          <p class="font-semibold">Chiqim yozildi · tannarx {{ fmt(issResult.total_cost) }} UZS</p>
          <p v-for="a in issResult.allocations" :key="a.batch_id">partiya {{ a.batch_no }} ({{ a.expires_on || 'muddatsiz' }}): {{ q(a.qty) }}</p>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Yopish</button><button class="btn-primary" :disabled="busy" data-testid="iss-save" @click="saveIssue">Chiqim qilish</button></div>
      </div>
    </div>

    <!-- Hisobdan chiqarish -->
    <div v-if="modal === 'writeoff'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-md')">
        <h3 :class="titleClass">Hisobdan chiqarish: {{ wo.batch.item }} ({{ wo.batch.batch_no }})</h3>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="lbl">Miqdor (qoldiq {{ q(wo.batch.qty_remaining) }})</label><input v-model.number="wo.qty" type="number" min="0" step="0.001" class="input" /></div>
          <div><label class="lbl">Sabab *</label><input v-model="wo.reason" class="input" placeholder="muddati o'tgan" data-testid="wo-reason" /></div>
        </div>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="wo-save" @click="saveWriteoff">Hisobdan chiqarish</button></div>
      </div>
    </div>

    <!-- Ko'chirish -->
    <div v-if="modal === 'transfer'" class="modal-overlay" @click.self="modal = ''">
      <div :class="boxClass('max-w-xl')">
        <h3 :class="titleClass">Boshqa filialga ko'chirish</h3>
        <div><label class="lbl">Qabul qiluvchi filial</label>
          <select v-model="trf.to_branch_id" class="input" data-testid="trf-to"><option value="" disabled>Tanlang</option><option v-for="b in otherBranches" :key="b.id" :value="b.id">{{ b.name }}</option></select></div>
        <div class="space-y-2">
          <div v-for="(l, i) in trf.lines" :key="i" class="grid grid-cols-12 gap-2">
            <select v-model="l.item_id" class="input col-span-7" data-testid="trf-item"><option value="" disabled>Material</option><option v-for="it in items" :key="it.id" :value="it.id">{{ it.name }} ({{ it.unit }})</option></select>
            <input v-model.number="l.qty" type="number" min="0" step="0.001" class="input col-span-4" placeholder="Miqdor" data-testid="trf-qty" />
            <button class="text-red-500 col-span-1" :disabled="trf.lines.length === 1" @click="trf.lines.splice(i, 1)"><Trash2 class="w-4 h-4" /></button>
          </div>
          <button class="text-xs text-cyan-600" @click="trf.lines.push({ item_id: '', qty: null })"><Plus class="w-3.5 h-3.5 inline" /> Qator qo'shish</button>
        </div>
        <input v-model="trf.notes" class="input" placeholder="Izoh (ixtiyoriy)" />
        <p class="text-xs text-slate-400">Qoldiq FEFO bo'yicha darhol kamayadi; qabul qiluvchi filial "Qabul qilish"ni bossa o'z omboriga tushadi.</p>
        <div class="flex justify-end gap-2"><button class="btn-secondary" @click="modal = ''">Bekor</button><button class="btn-primary" :disabled="busy" data-testid="trf-save" @click="saveTransfer">Yuborish</button></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { Plus, PackagePlus, PackageMinus, Truck, Trash2 } from 'lucide-vue-next'
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
const q = v => new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 3 }).format(v ?? 0)
const today = new Date().toISOString().slice(0, 10)

const tabs = [{ key: 'stock', label: 'Qoldiq' }, { key: 'batches', label: 'Partiyalar' }, { key: 'receipts', label: 'Kirim' },
  { key: 'movements', label: 'Harakatlar' }, { key: 'transfers', label: "Ko'chirish" }, { key: 'shortages', label: 'Yetishmovchilik' }]
const kindLabel = { Receipt: 'Kirim', Issue: 'Chiqim', Writeoff: 'Hisobdan chiqarish', TransferOut: "Ko'chirish (chiqim)", TransferIn: "Ko'chirish (kirim)", Adjust: 'Tuzatish', Consumption: 'Xizmat sarfi' }
const statusLabel = { Sent: "Yo'lda", Received: 'Qabul qilingan', Cancelled: 'Bekor qilingan' }
const statusClass = { Sent: 'badge-yellow', Received: 'badge-green', Cancelled: 'badge-slate' }

const tab = ref('stock'), loading = ref(true), error = ref(false), busy = ref(false), modal = ref('')
const items = ref([]), stock = ref([]), batches = ref([]), receipts = ref([]), movements = ref([]), transfers = ref([]), branches = ref([])
const alerts = reactive({ expiry_days: 30, low_stock: [], expiring: [], expired: [], shortages: [] })
const search = ref(''), lowOnly = ref(false), expOnly = ref(false)
const currentBranch = computed(() => branches.value.find(b => b.current)?.id)
const otherBranches = computed(() => branches.value.filter(b => !b.current))
const alertCount = computed(() => alerts.low_stock.length + alerts.expiring.length + alerts.expired.length + alerts.shortages.length)
const shownStock = computed(() => (lowOnly.value ? stock.value.filter(r => r.low) : stock.value))
const shownBatches = computed(() => (expOnly.value ? batches.value.filter(b => b.days_left != null && b.days_left <= alerts.expiry_days) : batches.value))

async function loadAlerts() {
  try { Object.assign(alerts, (await api.get('/warehouse/alerts')).data) } catch (e) { toast.error(e, "Ogohlantirishlarni yuklab bo'lmadi") }
}
async function loadTab() {
  loading.value = true; error.value = false
  try {
    if (tab.value === 'stock') stock.value = (await api.get('/warehouse/stock', { params: search.value ? { search: search.value } : {} })).data
    else if (tab.value === 'batches') batches.value = (await api.get('/warehouse/batches')).data
    else if (tab.value === 'receipts') receipts.value = (await api.get('/warehouse/receipts')).data
    else if (tab.value === 'movements') movements.value = (await api.get('/warehouse/movements', { params: { limit: 200 } })).data
    else if (tab.value === 'transfers') transfers.value = (await api.get('/warehouse/transfers')).data
  } catch (e) { error.value = true; toast.error(e, "Omborni yuklab bo'lmadi") } finally { loading.value = false }
}
async function refresh() { await Promise.all([loadTab(), loadAlerts()]) }
watch(tab, loadTab)

// Material
const itemForm = reactive({ id: null, name: '', kind: 'Supply', unit: '', sku: '', min_qty: 0, is_active: true })
function openItem(r) {
  Object.assign(itemForm, r ? { id: r.item_id, name: r.name, kind: r.kind, unit: r.unit, sku: r.sku || '', min_qty: r.min_qty, is_active: true }
    : { id: null, name: '', kind: 'Supply', unit: '', sku: '', min_qty: 0, is_active: true })
  modal.value = 'item'
}
async function saveItem() {
  busy.value = true
  const body = { name: itemForm.name, kind: itemForm.kind, unit: itemForm.unit, sku: itemForm.sku || null, min_qty: itemForm.min_qty || 0 }
  try {
    if (itemForm.id) await api.put(`/warehouse/items/${itemForm.id}`, { ...body, is_active: itemForm.is_active })
    else await api.post('/warehouse/items', body)
    toast.success('Material saqlandi'); modal.value = ''; await loadItems(); await refresh()
  } catch (e) { toast.error(e, "Materialni saqlab bo'lmadi") } finally { busy.value = false }
}
async function loadItems() { try { items.value = (await api.get('/warehouse/items')).data } catch (e) { toast.error(e, "Materiallar katalogini yuklab bo'lmadi") } }

// Kirim
const emptyLine = () => ({ item_id: '', batch_no: '', expires_on: '', qty: null, unit_cost: null })
const rcp = reactive({ supplier: '', doc_no: '', received_on: today, lines: [emptyLine()] })
function openReceipt() { Object.assign(rcp, { supplier: '', doc_no: '', received_on: today, lines: [emptyLine()] }); modal.value = 'receipt' }
async function saveReceipt() {
  busy.value = true
  try {
    await api.post('/warehouse/receipts', { supplier: rcp.supplier || null, doc_no: rcp.doc_no || null, received_on: rcp.received_on || null,
      lines: rcp.lines.map(l => ({ item_id: l.item_id, batch_no: l.batch_no, expires_on: l.expires_on || null, qty: l.qty, unit_cost: l.unit_cost ?? 0 })) })
    toast.success('Kirim saqlandi'); modal.value = ''; await refresh()
  } catch (e) { toast.error(e, "Kirimni saqlab bo'lmadi") } finally { busy.value = false }
}

// Chiqim
const iss = reactive({ item_id: '', qty: null, reason: '' }), issResult = ref(null)
function openIssue() { Object.assign(iss, { item_id: '', qty: null, reason: '' }); issResult.value = null; modal.value = 'issue' }
async function saveIssue() {
  busy.value = true
  try { issResult.value = (await api.post('/warehouse/issues', { item_id: iss.item_id, qty: iss.qty, reason: iss.reason })).data; await refresh() }
  catch (e) { issResult.value = null; toast.error(e, "Chiqimni yozib bo'lmadi") } finally { busy.value = false }
}

// Hisobdan chiqarish
const wo = reactive({ batch: {}, qty: null, reason: '' })
function openWriteoff(b) { Object.assign(wo, { batch: b, qty: b.qty_remaining, reason: b.expired ? "muddati o'tgan" : '' }); modal.value = 'writeoff' }
async function saveWriteoff() {
  busy.value = true
  try {
    await api.post('/warehouse/writeoffs', { batch_id: wo.batch.id, qty: wo.qty || null, reason: wo.reason })
    toast.success('Hisobdan chiqarildi'); modal.value = ''; await refresh()
  } catch (e) { toast.error(e, "Hisobdan chiqarib bo'lmadi") } finally { busy.value = false }
}

// Ko'chirish
const trf = reactive({ to_branch_id: '', notes: '', lines: [{ item_id: '', qty: null }] })
function openTransfer() { Object.assign(trf, { to_branch_id: '', notes: '', lines: [{ item_id: '', qty: null }] }); modal.value = 'transfer' }
async function saveTransfer() {
  busy.value = true
  try {
    await api.post('/warehouse/transfers', { to_branch_id: trf.to_branch_id, notes: trf.notes || null, lines: trf.lines.map(l => ({ item_id: l.item_id, qty: l.qty })) })
    toast.success('Hujjat yuborildi'); modal.value = ''; tab.value = 'transfers'; await refresh()
  } catch (e) { toast.error(e, "Ko'chirib bo'lmadi") } finally { busy.value = false }
}
async function receiveTransfer(t) {
  busy.value = true
  try { await api.post(`/warehouse/transfers/${t.id}/receive`); toast.success('Qabul qilindi'); await refresh() } catch (e) { toast.error(e, "Qabul qilib bo'lmadi") } finally { busy.value = false }
}
async function cancelTransfer(t) {
  const reason = window.prompt('Bekor qilish sababi:')
  if (!reason || reason.trim().length < 3) return
  try { await api.post(`/warehouse/transfers/${t.id}/cancel`, { reason }); toast.success('Bekor qilindi, qoldiq qaytdi'); await refresh() } catch (e) { toast.error(e, "Bekor qilib bo'lmadi") }
}
async function resolveShortage(s) {
  try { await api.post(`/warehouse/shortages/${s.id}/resolve`); toast.success('Ombordan yozildi'); await refresh() } catch (e) { toast.error(e, "Yozib bo'lmadi") }
}

onMounted(async () => {
  await loadItems()
  try { branches.value = (await api.get('/branches')).data } catch { branches.value = [] }
  await refresh()
})
</script>

<style scoped>
.lbl { display: block; font-size: 0.75rem; color: rgb(148 163 184); margin-bottom: 0.25rem; }
</style>
