<template>
  <div class="space-y-5 animate-fade-in">

    <!-- Header -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">Medical Records</h2>
        <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Create and manage patient records</p>
      </div>
      <div class="flex gap-2">
        <button class="btn-secondary text-sm" @click="exportExcel">
          <TableIcon class="w-4 h-4" /> Export Excel
        </button>
        <button class="btn-primary text-sm" @click="openNew">
          <Plus class="w-4 h-4" /> New Record
        </button>
      </div>
    </div>

    <!-- Search -->
    <div class="card">
      <div :class="['p-4 border-b', dark ? 'border-slate-800' : 'border-slate-100']">
        <div class="relative max-w-sm">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input v-model="search" class="input pl-9" placeholder="Search by patient or diagnosis..." />
        </div>
      </div>

      <!-- Records list -->
      <div :class="['divide-y', dark ? 'divide-slate-800' : 'divide-slate-100']">
        <div v-for="r in filtered" :key="r.id"
          :class="['p-5 transition-colors group', dark ? 'hover:bg-slate-800/40' : 'hover:bg-slate-50']">
          <div class="flex items-start justify-between gap-4">
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-sm font-bold text-white flex-shrink-0">
                {{ (r.patient_name || "?")[0] }}
              </div>
              <div class="min-w-0">
                <p :class="['font-semibold truncate', dark ? 'text-white' : 'text-slate-900']">{{ r.patient_name }}</p>
                <p :class="['text-xs mt-0.5', dark ? 'text-slate-500' : 'text-slate-400']">{{ r.doctor }} • {{ r.visit_date }}</p>
              </div>
            </div>
            <div class="flex items-center gap-2 flex-shrink-0">
              <span v-if="r.dmed_copied_at" class="badge-green text-xs" title="DMED ga qo'lda ko'chirilgan">DMED ✓</span>
              <span class="badge badge-blue text-xs">{{ r.icd_code || 'ICD-10' }}</span>
              <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button @click="cardFor = r" :class="['p-1.5 rounded-lg transition-colors', dark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-100']" title="DMED ko'rik kartasi (nusxalash, chop etish)">
                  <ClipboardCheck class="w-4 h-4" />
                </button>
                <button @click="openEdit(r)" :class="['p-1.5 rounded-lg transition-colors', dark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-100']" title="Edit">
                  <Pencil class="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          <!-- Details -->
          <div class="mt-3 pl-[52px] space-y-2">
            <div :class="['p-3 rounded-xl border', dark ? 'bg-red-900/10 border-red-800/30' : 'bg-red-50 border-red-100']">
              <span :class="['text-xs font-semibold', dark ? 'text-red-400' : 'text-red-600']">Diagnosis: </span>
              <span :class="['text-sm', dark ? 'text-slate-300' : 'text-slate-700']">{{ r.diagnosis }}</span>
            </div>
            <div :class="['p-3 rounded-xl border', dark ? 'bg-blue-900/10 border-blue-800/30' : 'bg-blue-50 border-blue-100']">
              <span :class="['text-xs font-semibold', dark ? 'text-blue-400' : 'text-blue-600']">Treatment: </span>
              <span :class="['text-sm', dark ? 'text-slate-300' : 'text-slate-700']">{{ r.prescription }}</span>
            </div>
            <!-- Symptoms -->
            <div v-if="r.symptoms?.length" class="flex flex-wrap gap-1.5">
              <span v-for="s in r.symptoms" :key="s"
                :class="['px-2.5 py-0.5 rounded-full text-xs font-medium', dark ? 'bg-slate-800 text-slate-300' : 'bg-slate-100 text-slate-600']">
                {{ s }}
              </span>
            </div>
          </div>
        </div>

        <EmptyState v-if="loadError" title="Tibbiy yozuvlarni yuklab bo'lmadi" description="Serverga ulanishni tekshirib, qayta urinib ko'ring" action-label="Qayta urinish" @action="loadRecords" />
        <div v-else-if="loading" :class="['py-16 text-center text-sm', dark ? 'text-slate-500' : 'text-slate-400']">Yuklanmoqda...</div>
        <EmptyState v-else-if="records.length === 0" title="Hali tibbiy yozuvlar yo'q" description="Birinchi tibbiy yozuvni yaratish uchun tugmani bosing" action-label="Yangi yozuv" @action="openNew" />
        <div v-else-if="filtered.length === 0" class="py-16 text-center">
          <FileText :class="['w-12 h-12 mx-auto mb-3', dark ? 'text-slate-700' : 'text-slate-300']" />
          <p :class="['text-sm', dark ? 'text-slate-500' : 'text-slate-400']">No records found</p>
        </div>
      </div>
    </div>

    <!-- ══════════════════════ FULLSCREEN FORM MODAL ══════════════════════════ -->
    <Transition name="modal-fade">
      <div v-if="showForm" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div :class="['w-full max-w-5xl rounded-2xl shadow-2xl flex flex-col animate-fade-in', dark ? 'bg-slate-900 border border-slate-800' : 'bg-white']"
          style="max-height: 94vh;">

          <!-- Form header -->
          <div :class="['flex items-center justify-between px-6 py-4 border-b flex-shrink-0', dark ? 'border-slate-800' : 'border-slate-200']">
            <h3 :class="['font-heading font-semibold text-lg', dark ? 'text-white' : 'text-slate-900']">
              {{ editingId ? 'Edit Medical Record' : 'New Medical Record' }}
            </h3>
            <div class="flex items-center gap-2">
              <button @click="saveDraft" class="btn-secondary text-sm"><Save class="w-4 h-4" />Save Draft</button>
              <button @click="printForm" class="btn-secondary text-sm"><Printer class="w-4 h-4" />Print</button>
              <button @click="closeForm" :class="['p-2 rounded-xl', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><X class="w-4 h-4" /></button>
            </div>
          </div>

          <!-- Form body — 2 columns -->
          <div class="flex flex-1 overflow-hidden">

            <!-- Left column -->
            <div class="flex-1 overflow-y-auto p-6 space-y-5 border-r" :class="dark ? 'border-slate-800' : 'border-slate-200'">

              <!-- Consultation Details -->
              <div :class="['rounded-2xl border p-5', dark ? 'border-slate-800 bg-slate-800/20' : 'border-slate-200 bg-slate-50/50']">
                <div class="flex items-center gap-2 mb-4">
                  <Stethoscope class="w-4 h-4 text-cyan-500" />
                  <h4 :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">Consultation Details</h4>
                </div>
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <label :class="lbl">Patient *</label>
                    <select v-model="form.patient_name" class="input">
                      <option value="">Select patient</option>
                      <option v-for="p in patientList" :key="p">{{ p }}</option>
                    </select>
                  </div>
                  <div>
                    <label :class="lbl">ICD Code</label>
                    <Icd10Input v-model="form.icd_code" @pick="c => { if (!form.diagnosis) form.diagnosis = c.name_uz }" />
                  </div>
                  <div>
                    <label :class="lbl">Doctor *</label>
                    <select v-model="form.doctor" class="input">
                      <option value="">Select doctor</option>
                      <option v-for="d in doctorList" :key="d">{{ d }}</option>
                    </select>
                  </div>
                  <div>
                    <label :class="lbl">Visit Date</label>
                    <input v-model="form.visit_date" type="date" class="input" />
                  </div>
                </div>
              </div>

              <!-- Ko'rik bo'limlari -->
              <div :class="['rounded-2xl border p-5 space-y-4', dark ? 'border-slate-800 bg-slate-800/20' : 'border-slate-200']">
                <div class="flex items-center justify-between gap-3 flex-wrap">
                  <h4 :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">Ko'rik bo'limlari</h4>
                  <select v-model="templateId" class="input w-auto text-xs" @change="applyTemplate">
                    <option value="">Shablon tanlash...</option>
                    <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
                  </select>
                </div>
                <div v-if="!editingId && apptOptions.length">
                  <label :class="lbl">Qabulga bog'lash (ko'rik saqlanganda qabul yakunlanadi)</label>
                  <select v-model="form.appointment_id" class="input">
                    <option value="">Bog'lanmagan</option>
                    <option v-for="a in apptOptions" :key="a.id" :value="a.id">{{ a.date }} {{ a.time }} · {{ a.type }} · {{ a.doctor }}</option>
                  </select>
                </div>
                <div>
                  <label :class="lbl">Qayta ko'rik (necha kundan keyin; bemorga eslatma ketadi, rozilik bo'lsa)</label>
                  <input v-model.number="form.recall_days" type="number" min="1" max="730" class="input w-40" placeholder="masalan 14" />
                </div>
                <div v-for="f in sectionFields" :key="f.key">
                  <label :class="lbl">{{ f.label }}</label>
                  <textarea v-model="form[f.key]" rows="3" class="input" />
                </div>
              </div>

              <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">Tanlangan simptomlar saqlanganda "Shikoyatlar" bo'limiga matn sifatida qo'shiladi</p>

              <!-- Symptoms -->
              <div :class="['rounded-2xl border p-5', dark ? 'border-slate-800 bg-slate-800/20' : 'border-slate-200']">
                <div class="flex items-center gap-2 mb-4">
                  <ClipboardCheck class="w-4 h-4 text-cyan-500" />
                  <h4 :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">Symptoms</h4>
                </div>
                <div class="flex flex-wrap gap-2">
                  <button v-for="sym in allSymptoms" :key="sym"
                    type="button"
                    @click="toggleSymptom(sym)"
                    :class="['px-3 py-1.5 rounded-full text-xs font-medium border transition-all',
                      form.symptoms.includes(sym)
                        ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                        : dark ? 'border-slate-700 text-slate-400 hover:border-slate-500' : 'border-slate-200 text-slate-600 hover:border-slate-300']">
                    {{ sym }}
                  </button>
                </div>
              </div>

              <!-- Diagnosis & Treatment -->
              <div :class="['rounded-2xl border p-5', dark ? 'border-slate-800 bg-slate-800/20' : 'border-slate-200']">
                <div class="flex items-center gap-2 mb-4">
                  <FileText class="w-4 h-4 text-cyan-500" />
                  <h4 :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">Diagnosis & Treatment</h4>
                </div>
                <div class="space-y-3">
                  <div>
                    <label :class="lbl">Diagnosis *</label>
                    <textarea v-model="form.diagnosis" class="input h-20 resize-none" placeholder="Enter diagnosis..."></textarea>
                  </div>
                  <div>
                    <label :class="lbl">Treatment Plan</label>
                    <textarea v-model="form.notes" class="input h-20 resize-none" placeholder="Enter treatment plan..."></textarea>
                  </div>
                </div>
              </div>

              <PrescriptionEditor v-model:rows="form.rxRows" :existing="existingRx" @cancel="cancelRx" />
            </div>

            <!-- Right column -->
            <div class="w-72 flex-shrink-0 overflow-y-auto p-5 space-y-4">

              <AttachmentsPanel v-if="editingId && formPatientId" :patient-id="formPatientId" :encounter-id="editingId" title="Ko'rik ilovalari" />
              <p v-else :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">Fayl (PDF, JPG, PNG, DICOM) ko'rik saqlangandan keyin biriktiriladi.</p>

              <!-- Save button -->
              <button type="button" class="btn-primary w-full justify-center" @click="saveRecord" :disabled="saving">
                <Save class="w-4 h-4" />{{ saving ? 'Saving...' : 'Save Medical Record' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Print template (hidden) -->
    <div id="print-area" class="hidden"></div>
    <EncounterCard v-if="cardFor" :record-id="cardFor.id" @close="cardFor = null" @marked="onMarked" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import Icd10Input from '@/components/Icd10Input.vue'
import PrescriptionEditor from '@/components/PrescriptionEditor.vue'
import EncounterCard from '@/components/EncounterCard.vue'
import AttachmentsPanel from '@/components/AttachmentsPanel.vue'
import { Plus, Search, X, Pencil, Save, Printer, FileText,
  Stethoscope, ClipboardCheck, TableIcon } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import api, { fetchAll } from '@/composables/useApi'
import { useToast } from '@/composables/useToast'
import EmptyState from '@/components/ui/EmptyState.vue'

const theme = useThemeStore()
const dark = computed(() => theme.isDark)
const lbl = computed(() => ['text-sm font-medium block mb-1.5', dark.value ? 'text-slate-300' : 'text-slate-700'])

const records = ref([])
const loading = ref(true)
const loadError = ref(false)
const search = ref('')
const showForm = ref(false)
const editingId = ref(null)
const saving = ref(false)

const allSymptoms = ['Fever', 'Headache', 'Cough', 'Fatigue', 'Chest Pain', 'Shortness of Breath', 'Nausea', 'Dizziness', 'Joint Pain', 'Sore Throat']
const toast = useToast()
const patientRows = ref([])
const patientList = computed(() => patientRows.value.map(p => p.name))
const doctorList = ref([])

const defaultForm = () => ({
  patient_name: '', doctor: '', visit_date: new Date().toISOString().slice(0, 10),
  icd_code: '', diagnosis: '', prescription: '', notes: '',
  complaints: '', anamnesis: '', examination: '', recommendations: '', appointment_id: '',
  rxRows: [],
  symptoms: [], medications: [], labFiles: [], attachments: []
})
const form = reactive(defaultForm())

const sectionFields = [
  { key: 'complaints', label: 'Shikoyatlar' }, { key: 'anamnesis', label: 'Anamnez' },
  { key: 'examination', label: "Ob'ektiv ko'rik" }, { key: 'recommendations', label: 'Tavsiyalar' },
]
const templates = ref([]), templateId = ref('')
function applyTemplate() {
  const t = templates.value.find(x => x.id === templateId.value)
  if (!t) return
  // mavjud matn ustiga yozilmaydi: faqat bo'sh bo'limlar to'ldiriladi
  for (const f of sectionFields) if (!form[f.key] && t[f.key]) form[f.key] = t[f.key]
  if (!form.diagnosis && t.diagnosis) form.diagnosis = t.diagnosis
}
// Eski simptom chiplari "Shikoyatlar" bo'limiga matn sifatida tushadi
function withSymptoms(text, symptoms) {
  if (!symptoms.length) return text
  const line = `Simptomlar: ${symptoms.join(', ')}`
  return text && text.includes(line) ? text : [text, line].filter(Boolean).join('\n')
}
const cardFor = ref(null)
const formPatientId = computed(() => patientRows.value.find(p => p.name === form.patient_name)?.id || '')
function onMarked(at) { const r = records.value.find(x => x.id === cardFor.value?.id); if (r) r.dmed_copied_at = at }
const existingRx = ref([])
async function cancelRx(p) {
  try {
    await api.delete(`/prescriptions/${p.id}`)
    existingRx.value = existingRx.value.filter(x => x.id !== p.id)
    toast.success('Retsept bekor qilindi')
  } catch (e) { toast.error(e, "Retseptni bekor qilib bo'lmadi") }
}
async function postRx(recordId) {
  const valid = form.rxRows.filter(r => r.inn.trim())
  for (const r of valid) {
    await api.post(`/emr/${recordId}/prescriptions`, {
      inn: r.inn, dose: r.dose, route: r.route, frequency: r.frequency, duration_days: r.duration_days, instructions: r.instructions || null,
    })
  }
  return valid.length
}
const apptOptions = ref([])
watch(() => form.patient_name, async name => {
  form.appointment_id = ''
  const patient = patientRows.value.find(p => p.name === name)
  if (!patient) { apptOptions.value = []; return }
  try {
    apptOptions.value = (await api.get('/appointments', { params: { patient_id: patient.id, status: 'Scheduled' } })).data
  } catch { apptOptions.value = [] }
})

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return records.value
  return records.value.filter(r => r.patient_name.toLowerCase().includes(q) || r.diagnosis.toLowerCase().includes(q))
})

function toggleSymptom(s) {
  const i = form.symptoms.indexOf(s)
  i >= 0 ? form.symptoms.splice(i, 1) : form.symptoms.push(s)
}



function openNew() { editingId.value = null; existingRx.value = []; Object.assign(form, defaultForm()); showForm.value = true }
function openEdit(r) {
  editingId.value = r.id
  existingRx.value = [...(r.prescriptions || [])]
  Object.assign(form, { patient_name: r.patient_name, doctor: r.doctor, visit_date: r.visit_date,
    icd_code: r.icd_code || '', diagnosis: r.diagnosis, prescription: r.prescription, notes: r.notes || '',
    complaints: r.complaints || '', anamnesis: r.anamnesis || '', examination: r.examination || '',
    recommendations: r.recommendations || '', appointment_id: '',
    symptoms: [...(r.symptoms || [])], medications: [...(r.medications || [])],
    labFiles: [...(r.labFiles || [])], attachments: [...(r.attachments || [])] })
  showForm.value = true
}
function closeForm() { showForm.value = false }

function saveDraft() {
  const draft = { ...form, id: editingId.value || Date.now().toString(), isDraft: true }
  console.log('Draft saved', draft)
}

async function saveRecord() {
  if (!form.patient_name || !form.diagnosis || !form.doctor) return
  const patient = patientRows.value.find(p => p.name === form.patient_name)
  if (!patient) { toast.error('Bemor topilmadi'); return }
  saving.value = true
  try {
    const payload = { patient_id: patient.id, patient_name: patient.name, doctor: form.doctor,
                      icd_code: form.icd_code || null, diagnosis: form.diagnosis, prescription: form.prescription || '-',
                      notes: form.notes || null, visit_date: form.visit_date,
                      complaints: withSymptoms(form.complaints, form.symptoms) || null, anamnesis: form.anamnesis || null,
                      examination: form.examination || null, recommendations: form.recommendations || null,
                      appointment_id: form.appointment_id || null, recall_days: form.recall_days || null }
    // tahrirlashda ko'rik yangilanadi (yangi yozuv yaratilmaydi); retsept alohida boshqariladi
    const { data } = editingId.value
      ? await api.put(`/emr/${editingId.value}`, { diagnosis: form.diagnosis, icd_code: form.icd_code || null, notes: form.notes || null,
          complaints: payload.complaints, anamnesis: payload.anamnesis, examination: payload.examination, recommendations: payload.recommendations, recall_days: payload.recall_days })
      : await api.post('/emr', payload)
    // Backend saqlamaydigan maydonlar (simptomlar, dorilar, fayllar) faqat ekranda qoladi
    const merged = { ...JSON.parse(JSON.stringify(form)), ...data }
    const idx = records.value.findIndex(r => r.id === data.id)
    if (idx >= 0) records.value[idx] = { ...records.value[idx], ...merged }
    else records.value.unshift(merged)
    try {
      const added = await postRx(data.id)
      if (added) await loadRecords()
    } catch (e) {
      // ko'rik saqlandi, retsept yo'q: forma ochiq qoladi (tahrirlash rejimida), shifokor tuzatib qayta saqlaydi
      editingId.value = data.id
      form.rxRows = []
      existingRx.value = (await api.get(`/emr/${data.id}/prescriptions`)).data
      toast.error(e, "Ko'rik saqlandi, lekin retseptni saqlab bo'lmadi")
      return
    }
    toast.success('Yozuv saqlandi')
    closeForm()
  } catch (e) {
    toast.error(e, "Yozuvni saqlab bo'lmadi")
  } finally {
    saving.value = false
  }
}

function printRecord(r) {
  const w = window.open('', '_blank')
  w.document.write(`
    <html><head><title>Medical Record</title>
    <style>body{font-family:sans-serif;padding:20px;max-width:800px;margin:auto}
    h1{font-size:20px;border-bottom:2px solid #0ea5e9;padding-bottom:8px}
    .section{margin:16px 0;padding:12px;border:1px solid #e2e8f0;border-radius:8px}
    .label{font-weight:600;color:#0ea5e9;font-size:12px;text-transform:uppercase}
    .chip{display:inline-block;background:#e2e8f0;border-radius:20px;padding:2px 10px;margin:2px;font-size:12px}
    </style></head><body>
    <h1>Medical Record — ${r.patient_name}</h1>
    <div class="section"><div class="label">Patient</div><p>${r.patient_name}</p>
    <div class="label">Doctor</div><p>${r.doctor}</p>
    <div class="label">Date</div><p>${r.visit_date}</p>
    ${r.icd_code ? `<div class="label">ICD Code</div><p>${r.icd_code}</p>` : ''}
    </div>
    ${r.symptoms?.length ? `<div class="section"><div class="label">Symptoms</div><br>${r.symptoms.map(s => `<span class="chip">${s}</span>`).join('')}</div>` : ''}
    <div class="section"><div class="label">Diagnosis</div><p>${r.diagnosis}</p>
    ${r.prescription ? `<div class="label">Treatment</div><p>${r.prescription}</p>` : ''}
    ${r.notes ? `<div class="label">Notes</div><p>${r.notes}</p>` : ''}
    </div>
    ${r.medications?.length ? `<div class="section"><div class="label">Medications</div>
    ${r.medications.map(m => `<p>${m.name} — ${m.dose} — ${m.days}</p>`).join('')}</div>` : ''}
    </body></html>`)
  w.document.close(); w.print()
}

function printForm() {
  const temp = { patient_name: form.patient_name, doctor: form.doctor, visit_date: form.visit_date, icd_code: form.icd_code, diagnosis: form.diagnosis, prescription: form.prescription, notes: form.notes, symptoms: form.symptoms, medications: form.medications }
  printRecord(temp)
}

function exportExcel() {
  const header = ['Patient', 'Doctor', 'Date', 'ICD Code', 'Diagnosis', 'Treatment', 'Symptoms']
  const rows = records.value.map(r => [r.patient_name, r.doctor, r.visit_date, r.icd_code || '', r.diagnosis, r.prescription, (r.symptoms || []).join('; ')])
  const csv = [header, ...rows].map(r => r.map(c => `"${c}"`).join(',')).join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' }))
  a.download = `EMR_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
}

async function loadRecords() {
  loading.value = true
  loadError.value = false
  try {
    const { data } = await api.get('/emr')
    records.value = data
  } catch (e) {
    records.value = []
    loadError.value = true
    toast.error(e, "Tibbiy yozuvlarni yuklab bo'lmadi")
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try { patientRows.value = await fetchAll('/patients') } catch (e) { toast.error(e, "Bemorlar ro'yxatini yuklab bo'lmadi") }
  try {
    const { data } = await api.get('/staff', { params: { role: 'Doctor' } })
    doctorList.value = data.map(s => s.name)
  } catch (e) { toast.error(e, "Shifokorlar ro'yxatini yuklab bo'lmadi") }
  try { templates.value = (await api.get('/emr-templates')).data } catch (e) { toast.error(e, "Shablonlarni yuklab bo'lmadi") }
  await loadRecords()
})
</script>

<style scoped>
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
</style>