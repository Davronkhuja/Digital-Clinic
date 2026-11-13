<template>
  <div class="space-y-6 animate-fade-in">
    <div class="flex items-center gap-3">
      <RouterLink to="/patients" class="btn-ghost !px-2 !py-2"><ChevronLeft class="w-5 h-5" /></RouterLink>
      <div>
        <h2 class="text-2xl font-heading font-bold text-slate-900">Bemor Profili</h2>
        <p class="text-slate-500 text-sm">Bemor ID: #{{ $route.params.id }}</p>
      </div>
    </div>

    <div v-if="patient" class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <!-- Profile card -->
      <div class="card p-6 flex flex-col items-center text-center">
        <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-3xl font-bold text-white mb-4">
          {{ patient.name[0] }}
        </div>
        <h3 class="font-heading text-xl font-bold text-slate-900">{{ patient.name }}</h3>
        <p class="text-slate-500 text-sm mt-1">{{ patient.phone }}</p>
        <span :class="patient.status === 'Active' ? 'badge-green' : 'badge-slate'" class="mt-3">
          {{ patient.status === 'Active' ? 'Faol' : 'Nofaol' }}
        </span>

        <div class="w-full mt-6 space-y-3 text-left">
          <div class="flex items-center justify-between py-2 border-b border-slate-100">
            <span class="text-xs text-slate-500">Yosh</span>
            <span class="text-sm font-medium text-slate-900">{{ patient.age }} yosh</span>
          </div>
          <div class="flex items-center justify-between py-2 border-b border-slate-100">
            <span class="text-xs text-slate-500">Jins</span>
            <span class="text-sm font-medium text-slate-900">{{ patient.gender === 'male' ? 'Erkak' : 'Ayol' }}</span>
          </div>
          <div class="flex items-center justify-between py-2 border-b border-slate-100">
            <span class="text-xs text-slate-500">Qon guruhi</span>
            <span class="text-sm font-medium text-red-500">{{ patient.blood_type || 'N/A' }}</span>
          </div>
          <div class="flex items-center justify-between py-2 border-b border-slate-100">
            <span class="text-xs text-slate-500">Shifokor</span>
            <span class="text-sm font-medium text-slate-900">{{ patient.doctor || '—' }}</span>
          </div>
          <div v-if="patient.address" class="flex items-center justify-between py-2">
            <span class="text-xs text-slate-500">Manzil</span>
            <span class="text-sm font-medium text-slate-900">{{ patient.address }}</span>
          </div>
        </div>

        <div class="flex gap-2 w-full mt-6">
          <RouterLink :to="`/appointments?patient=${patient.id}`" class="btn-primary flex-1 text-xs justify-center">Uchrashuv</RouterLink>
          <RouterLink :to="`/emr?patient=${patient.id}`" class="btn-secondary flex-1 text-xs justify-center">EMR</RouterLink>
        </div>
      </div>

      <!-- Visits & records -->
      <div class="lg:col-span-2 space-y-4">
        <div class="card p-5">
          <h4 class="font-heading font-semibold text-slate-900 mb-3">Tibbiy tarix</h4>
          <div class="space-y-3">
            <div v-for="record in emrRecords" :key="record.id" class="p-4 rounded-xl bg-slate-50 border border-slate-100">
              <div class="flex items-start justify-between">
                <div>
                  <p class="font-medium text-slate-900 text-sm">{{ record.diagnosis }}</p>
                  <p class="text-xs text-slate-500 mt-0.5">{{ record.doctor }} • {{ record.visit_date }}</p>
                </div>
                <span class="badge badge-blue text-xs">{{ record.visit_date }}</span>
              </div>
              <div class="mt-2 p-2.5 rounded-lg bg-white border border-slate-200">
                <p class="text-xs text-slate-500 font-medium mb-1">Retsept:</p>
                <p class="text-xs text-slate-700">{{ record.prescription }}</p>
              </div>
            </div>
            <p v-if="emrRecords.length === 0" class="text-center text-slate-400 py-6 text-sm">Tibbiy yozuv topilmadi</p>
          </div>
        </div>

        <div class="card p-5">
          <h4 class="font-heading font-semibold text-slate-900 mb-3">Uchrashuvlar tarixi</h4>
          <div class="space-y-2">
            <div v-for="appt in appointments" :key="appt.id" class="flex items-center justify-between p-3 rounded-xl bg-slate-50">
              <div>
                <p class="text-sm font-medium text-slate-900">{{ appt.type }}</p>
                <p class="text-xs text-slate-500">{{ appt.doctor }} • {{ appt.date }} {{ appt.time }}</p>
              </div>
              <span :class="{
                'badge-green': appt.status === 'Completed',
                'badge-blue': appt.status === 'Scheduled',
                'badge-red': appt.status === 'Cancelled',
              }">{{ appt.status }}</span>
            </div>
            <p v-if="appointments.length === 0" class="text-center text-slate-400 py-4 text-sm">Uchrashuvlar topilmadi</p>
          </div>
        </div>
        <ConsentCard :patient-id="patient.id" />
        <AttachmentsPanel v-if="auth.can('emr:read')" :patient-id="patient.id" title="Bemor fayllari (barcha ilovalar)" />
      </div>
    </div>

    <div v-else-if="notFound" class="card">
      <EmptyState title="Bemor topilmadi" description="Bunday bemor mavjud emas yoki o'chirilgan." />
    </div>

    <div v-else-if="loadError" class="card">
      <EmptyState title="Bemorni yuklab bo'lmadi" description="Server bilan aloqa o'rnatilmadi. Qayta urinib ko'ring." action-label="Qayta urinish" @action="load" />
    </div>

    <div v-else class="flex items-center justify-center h-64">
      <div class="text-center text-slate-400">
        <div class="animate-spin w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full mx-auto mb-3"></div>
        Yuklanmoqda...
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { ChevronLeft } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/ui/EmptyState.vue'
import AttachmentsPanel from '@/components/AttachmentsPanel.vue'
import ConsentCard from '@/components/ConsentCard.vue'
import { useAuthStore } from '@/stores/auth'

const toast = useToast()

const route = useRoute()
const auth = useAuthStore()
const patient = ref(null)
const emrRecords = ref([])
const appointments = ref([])
const notFound = ref(false)
const loadError = ref(false)

async function load() {
  const id = route.params.id
  patient.value = null
  notFound.value = false
  loadError.value = false
  try {
    const { data } = await api.get(`/patients/${id}`)
    patient.value = data
  } catch (e) {
    // Xatoda hech qachon boshqa bemor ma'lumoti ko'rsatilmaydi
    if (e?.response?.status === 404) notFound.value = true
    else {
      loadError.value = true
      toast.error(e, "Bemorni yuklab bo'lmadi")
    }
    return
  }

  try {
    const { data } = await api.get('/emr', { params: { patient_id: id } })
    emrRecords.value = data
  } catch (e) {
    emrRecords.value = []
    toast.error(e, "Tibbiy tarixni yuklab bo'lmadi")
  }

  try {
    const { data } = await api.get('/appointments', { params: { patient_id: id } })
    appointments.value = data
  } catch (e) {
    appointments.value = []
    toast.error(e, "Uchrashuvlarni yuklab bo'lmadi")
  }
}

onMounted(load)
</script>
