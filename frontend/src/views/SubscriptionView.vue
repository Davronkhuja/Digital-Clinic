<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Subscription & Billing</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Manage your plan and payments</p>
    </div>

    <!-- Current plan banner -->
    <div :class="['card p-5', dark ? 'bg-slate-900' : 'bg-white']">
      <div class="flex items-center justify-between gap-4 flex-wrap">
        <div class="flex items-center gap-4">
          <div class="w-11 h-11 rounded-xl bg-blue-600 flex items-center justify-center shadow-lg">
            <Zap class="w-6 h-6 text-white" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 :class="['font-heading font-bold text-lg', dark ? 'text-white' : 'text-slate-900']">Professional Plan</h3>
              <span class="badge bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400">Current</span>
            </div>
            <p :class="['text-sm', dark ? 'text-slate-400' : 'text-slate-500']">$49/month • Renews March 1, 2026</p>
          </div>
        </div>
        <button class="btn-secondary text-sm">Manage Plan</button>
      </div>

      <!-- Usage bars -->
      <div :class="['mt-5 pt-5 border-t grid grid-cols-1 sm:grid-cols-3 gap-6', dark ? 'border-slate-800' : 'border-slate-100']">
        <div v-for="u in usage" :key="u.label">
          <div class="flex justify-between items-center mb-1.5">
            <span :class="['text-xs font-medium', dark ? 'text-slate-400' : 'text-slate-500']">{{ u.label }}</span>
            <span :class="['text-xs font-semibold', dark ? 'text-slate-300' : 'text-slate-700']">{{ u.used }} / {{ u.total }}</span>
          </div>
          <div :class="['h-2 rounded-full overflow-hidden', dark ? 'bg-slate-700' : 'bg-slate-100']">
            <div class="h-full rounded-full bg-gradient-to-r from-blue-500 to-blue-600 transition-all duration-700"
              :style="{ width: `${(u.used / u.total) * 100}%` }"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Plans -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div v-for="plan in plans" :key="plan.name"
        :class="['rounded-2xl border p-6 relative transition-all',
          plan.current
            ? 'border-blue-500 ring-2 ring-blue-500/30 ' + (dark ? 'bg-slate-900' : 'bg-white')
            : dark ? 'bg-slate-900 border-slate-800 hover:border-slate-700' : 'bg-white border-slate-200 hover:border-slate-300']">

        <div class="mb-4">
          <p :class="['text-sm font-semibold', dark ? 'text-slate-400' : 'text-slate-500']">{{ plan.name }}</p>
          <div class="flex items-baseline gap-1 mt-1">
            <span :class="['text-4xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ plan.price }}</span>
            <span v-if="plan.period" :class="['text-sm', dark ? 'text-slate-400' : 'text-slate-500']">/mo</span>
          </div>
        </div>

        <ul class="space-y-2.5 mb-6">
          <li v-for="f in plan.features" :key="f" class="flex items-center gap-2.5 text-sm">
            <Check class="w-4 h-4 text-emerald-500 flex-shrink-0" />
            <span :class="dark ? 'text-slate-300' : 'text-slate-600'">{{ f }}</span>
          </li>
        </ul>

        <button :class="[
          'w-full flex items-center justify-center py-2.5 px-4 rounded-xl font-medium text-sm transition-all',
          plan.current
            ? dark ? 'bg-slate-800 text-slate-400 cursor-default' : 'bg-slate-100 text-slate-400 cursor-default'
            : 'bg-blue-600 hover:bg-blue-700 text-white shadow-sm'
        ]" :disabled="plan.current">
          {{ plan.current ? 'Current Plan' : 'Upgrade' }}
        </button>
      </div>
    </div>

    <!-- Billing history -->
    <div class="card">
      <div :class="['flex items-center gap-2 px-5 py-4 border-b', dark ? 'border-slate-800' : 'border-slate-100']">
        <CreditCard :class="['w-4 h-4', dark ? 'text-slate-400' : 'text-slate-500']" />
        <h3 :class="['font-heading font-semibold', dark ? 'text-white' : 'text-slate-900']">Billing History</h3>
      </div>
      <div class="table-container rounded-none border-0">
        <table class="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Invoice</th>
              <th>Amount</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="inv in invoices" :key="inv.id">
              <td :class="['font-mono text-sm', dark ? 'text-slate-400' : 'text-slate-600']">{{ inv.date }}</td>
              <td :class="['font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">{{ inv.invoice }}</td>
              <td :class="['font-semibold', dark ? 'text-slate-200' : 'text-slate-800']">{{ inv.amount }}</td>
              <td><span class="badge-green">{{ inv.status }}</span></td>
              <td>
                <button @click="downloadInvoice(inv)" :class="['p-2 rounded-lg transition-colors', dark ? 'text-slate-400 hover:bg-slate-800 hover:text-white' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-700']">
                  <Download class="w-4 h-4" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Check, Zap, CreditCard, Download } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
const dark = computed(() => theme.isDark)

const usage = [
  { label: 'Doctors Used', used: 3, total: 10 },
  { label: 'Patients', used: 128, total: 1000 },
  { label: 'Storage (GB)', used: 2.5, total: 10 },
]

const plans = [
  { name: 'Starter', price: 'Free', period: false, current: false, features: ['2 Doctors', '100 Patients', 'Basic Reports', 'Email Support'] },
  { name: 'Professional', price: '$49', period: true, current: true, features: ['10 Doctors', '1,000 Patients', 'Advanced Analytics', 'Priority Support', 'API Access'] },
  { name: 'Enterprise', price: '$149', period: true, current: false, features: ['Unlimited Doctors', 'Unlimited Patients', 'AI Features', '24/7 Support', 'Custom Integrations', 'Multi-branch'] },
]

const invoices = [
  { id: 1, date: '2026-02-01', invoice: 'INV-2026-02', amount: '$49.00', status: 'Paid' },
  { id: 2, date: '2026-01-01', invoice: 'INV-2026-01', amount: '$49.00', status: 'Paid' },
  { id: 3, date: '2025-12-01', invoice: 'INV-2025-12', amount: '$49.00', status: 'Paid' },
]

function downloadInvoice(inv) {
  const content = `Invoice: ${inv.invoice}\nDate: ${inv.date}\nAmount: ${inv.amount}\nStatus: ${inv.status}`
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([content], { type: 'text/plain' }))
  a.download = `${inv.invoice}.txt`
  a.click()
}
</script>