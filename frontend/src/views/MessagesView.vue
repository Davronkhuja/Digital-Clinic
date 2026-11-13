<template>
  <div class="space-y-6 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Xabarlar</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Yuborilgan va yuborilmagan xabarlar, qayta urinishlar, SMS hisobi</p>
    </div>
    <div v-if="stats" class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div class="card p-4"><p class="text-xs text-slate-400">SMS (30 kun)</p><p class="text-2xl font-bold">{{ stats.sms_messages }}</p><p class="text-xs text-slate-400">{{ stats.sms_segments }} qism (xarajat)</p></div>
      <div class="card p-4"><p class="text-xs text-slate-400">Telegram</p><p class="text-2xl font-bold">{{ stats.telegram_messages }}</p></div>
      <div class="card p-4"><p class="text-xs text-slate-400">Yuborildi / Xato</p><p class="text-2xl font-bold">{{ stats.by_status.Sent || 0 }} / <span class="text-red-500">{{ stats.by_status.Failed || 0 }}</span></p></div>
      <div class="card p-4"><p class="text-xs text-slate-400">Navbatda / O'tkazildi</p><p class="text-2xl font-bold">{{ stats.by_status.Queued || 0 }} / {{ stats.by_status.Skipped || 0 }}</p></div>
    </div>
    <div class="card">
      <div :class="['p-4 border-b flex gap-3 flex-wrap', dark ? 'border-slate-800' : 'border-slate-100']">
        <select v-model="status" class="input w-auto" @change="load"><option value="">Barcha holat</option><option v-for="(l, k) in statusLabel" :key="k" :value="k">{{ l }}</option></select>
        <select v-model="kind" class="input w-auto" @change="load"><option value="">Barcha tur</option><option v-for="k in kinds" :key="k" :value="k">{{ k }}</option></select>
      </div>
      <p v-if="loading" class="p-8 text-center text-sm text-slate-400">Yuklanmoqda...</p>
      <EmptyState v-else-if="error" title="Xabarlarni yuklab bo'lmadi" action-label="Qayta urinish" @action="load" />
      <EmptyState v-else-if="!items.length" title="Xabar yo'q" />
      <div v-else class="table-container rounded-none border-0">
        <table class="table">
          <thead><tr><th>Vaqt</th><th>Bemor</th><th>Kanal</th><th>Tur</th><th>Holat</th><th>Urinish</th><th>Matn</th></tr></thead>
          <tbody>
            <tr v-for="m in items" :key="m.id">
              <td class="font-mono text-xs">{{ (m.sent_at || m.scheduled_at).slice(0, 16).replace('T', ' ') }}</td>
              <td class="text-sm">{{ m.patient_name || '—' }}</td>
              <td><span class="badge-slate">{{ m.channel }}</span><span v-if="m.sms_segments" class="text-xs text-slate-400 ml-1">{{ m.sms_segments }} qism</span></td>
              <td class="text-xs">{{ m.kind }}</td>
              <td><span :class="statusClass[m.status]">{{ statusLabel[m.status] }}</span><span v-if="m.skip_reason || m.last_error" class="block text-[10px] text-slate-400">{{ m.skip_reason || m.last_error }}</span></td>
              <td class="text-sm">{{ m.attempts }}</td>
              <td class="text-xs text-slate-500 max-w-xs truncate" :title="m.body">{{ m.body }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import { useThemeStore } from '@/stores/theme'
import EmptyState from '@/components/ui/EmptyState.vue'

const toast = useToast(), theme = useThemeStore()
const dark = computed(() => theme.isDark)
const statusLabel = { Queued: 'Navbatda', Sent: 'Yuborildi', Failed: 'Xato', Skipped: "O'tkazildi" }
const statusClass = { Queued: 'badge-yellow', Sent: 'badge-green', Failed: 'badge-red', Skipped: 'badge-slate' }
const kinds = ['reminder_24h', 'reminder_2h', 'waitlist_offer', 'booking_confirmation', 'recall', 'otp']
const items = ref([]), stats = ref(null), loading = ref(true), error = ref(false), status = ref(''), kind = ref('')

async function load() {
  loading.value = true; error.value = false
  try {
    items.value = (await api.get('/messages', { params: { limit: 200, ...(status.value ? { status: status.value } : {}), ...(kind.value ? { kind: kind.value } : {}) } })).data
    stats.value = (await api.get('/messages/stats')).data
  } catch (e) { items.value = []; error.value = true; toast.error(e, "Xabarlarni yuklab bo'lmadi") } finally { loading.value = false }
}
onMounted(load)
</script>
