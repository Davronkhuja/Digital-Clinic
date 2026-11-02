<template>
  <div class="space-y-5 animate-fade-in">
    <div>
      <h2 :class="['text-2xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">AI Yordamchi</h2>
      <p :class="['text-sm mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Tibbiy savollarga AI yordamida javob oling</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">

      <!-- ═══ Chat Area ════════════════════════════════════════════════════ -->
      <div :class="['lg:col-span-2 card flex flex-col', dark ? '' : '']" style="height:620px">

        <!-- Messages -->
        <div ref="messagesEl" class="flex-1 overflow-y-auto p-5 space-y-4">

          <!-- Welcome screen -->
          <div v-if="messages.length === 0" class="flex flex-col items-center justify-center h-full text-center px-6">
            <div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-4 shadow-lg"
              :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
              <Bot class="w-8 h-8 text-white" />
            </div>
            <h3 :class="['font-heading font-bold text-xl', dark ? 'text-white' : 'text-slate-900']">Digital Clinic AI</h3>
            <p :class="['text-sm mt-2 max-w-xs leading-relaxed', dark ? 'text-slate-400' : 'text-slate-500']">
              Tibbiy savollaringizni bering. Groq LLaMA 3.1 modeli asosida ishlaydi.
            </p>
            <div class="mt-5 flex flex-wrap gap-2 justify-center">
              <button v-for="q in quickQuestions" :key="q"
                @click="sendQuick(q)"
                :class="['px-3 py-1.5 rounded-xl text-sm border transition-all hover:scale-[1.02]', dark ? 'border-slate-700 text-slate-300 hover:bg-slate-800' : 'border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300']">
                {{ q }}
              </button>
            </div>
          </div>

          <!-- Messages -->
          <div v-for="msg in messages" :key="msg.id" :class="['flex gap-3', msg.role === 'user' ? 'flex-row-reverse' : '']">
            <!-- Avatar -->
            <div v-if="msg.role === 'assistant'"
              class="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-1 shadow"
              :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
              <Bot class="w-4 h-4 text-white" />
            </div>
            <div v-else :class="['w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 mt-1 text-xs font-bold', dark ? 'bg-slate-700 text-slate-300' : 'bg-slate-200 text-slate-600']">
              {{ userInitial }}
            </div>

            <!-- Bubble -->
            <div class="flex flex-col max-w-[78%] gap-1">
              <div :class="[
                'px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap',
                msg.role === 'user'
                  ? 'rounded-tr-sm text-white'
                  : dark ? 'rounded-tl-sm bg-slate-800 text-slate-100' : 'rounded-tl-sm bg-slate-100 text-slate-800'
              ]" :style="msg.role === 'user' ? `background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))` : ''">
                {{ msg.content }}
              </div>
              <span :class="['text-[10px] px-1', msg.role === 'user' ? 'text-right' : '', dark ? 'text-slate-600' : 'text-slate-400']">{{ msg.time }}</span>
            </div>
          </div>

          <!-- Typing indicator -->
          <div v-if="typing" class="flex gap-3">
            <div class="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 shadow"
              :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
              <Bot class="w-4 h-4 text-white" />
            </div>
            <div :class="['rounded-2xl rounded-tl-sm px-4 py-3', dark ? 'bg-slate-800' : 'bg-slate-100']">
              <div class="flex gap-1 items-center h-4">
                <span class="w-2 h-2 rounded-full animate-bounce" :style="`background:rgb(var(--c-primary))`" style="animation-delay:0ms"></span>
                <span class="w-2 h-2 rounded-full animate-bounce" :style="`background:rgb(var(--c-primary))`" style="animation-delay:150ms"></span>
                <span class="w-2 h-2 rounded-full animate-bounce" :style="`background:rgb(var(--c-primary))`" style="animation-delay:300ms"></span>
              </div>
            </div>
          </div>

          <!-- Error -->
          <div v-if="error" :class="['flex items-center gap-3 p-3 rounded-xl border', dark ? 'bg-red-900/20 border-red-800/40 text-red-400' : 'bg-red-50 border-red-200 text-red-600']">
            <AlertCircle class="w-4 h-4 flex-shrink-0" />
            <p class="text-sm">{{ error }}</p>
          </div>
        </div>

        <!-- Disclaimer -->
        <div :class="['px-4 py-2 border-t text-[11px] text-center', dark ? 'border-slate-800 text-slate-600' : 'border-slate-100 text-slate-400']">
          ⚠️ Bu AI tibbiy maslahat emas. Iltimos, shifokorga murojaat qiling.
        </div>

        <!-- Input bar -->
        <div :class="['flex items-end gap-2 px-4 py-3 border-t', dark ? 'border-slate-800' : 'border-slate-200']">
          <button @click="clearChat" :class="['p-2.5 rounded-xl transition-colors flex-shrink-0', dark ? 'text-slate-500 hover:bg-slate-800 hover:text-white' : 'text-slate-400 hover:bg-slate-100']" title="Tozalash">
            <RotateCcw class="w-4 h-4" />
          </button>
          <div class="flex-1">
            <textarea
              ref="inputEl"
              v-model="inputText"
              @keydown.enter.exact.prevent="send"
              @keydown.enter.shift.exact="inputText += '\n'"
              @input="autoResize"
              :disabled="typing"
              :class="['w-full resize-none rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors', dark ? 'bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 focus:border-current' : 'bg-slate-50 border-slate-200 text-slate-900 focus:border-current', typing ? 'opacity-60 cursor-not-allowed' : '']"
              :style="`--tw-border-opacity:1; border-color:${inputText.trim() ? 'rgb(var(--c-primary))' : ''}`"
              placeholder="Savol yozing... (Enter — yuborish)"
              rows="1"
              style="max-height:100px"
            ></textarea>
          </div>
          <button @click="send" :disabled="!inputText.trim() || typing"
            :class="['p-2.5 rounded-xl transition-all flex-shrink-0 shadow-sm', !inputText.trim() || typing ? dark ? 'bg-slate-800 text-slate-600' : 'bg-slate-100 text-slate-300' : 'text-white hover:scale-105']"
            :style="inputText.trim() && !typing ? `background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))` : ''">
            <Send class="w-5 h-5" />
          </button>
        </div>
      </div>

      <!-- ═══ Sidebar: Info + Suggestions ══════════════════════════════════ -->
      <div class="space-y-4">
        <!-- Model info -->
        <div class="card p-5">
          <div class="flex items-center gap-3 mb-4">
            <div class="w-10 h-10 rounded-xl flex items-center justify-center"
              :style="`background:linear-gradient(135deg,rgb(var(--c-primary)/.15),rgb(var(--c-secondary)/.1))`">
              <Cpu :class="['w-5 h-5']" :style="`color:rgb(var(--c-primary))`" />
            </div>
            <div>
              <p :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">Model</p>
              <p class="text-xs font-mono" :style="`color:rgb(var(--c-primary))`">LLaMA 3.1-8B</p>
            </div>
          </div>
          <div class="space-y-2">
            <div v-for="s in modelStats" :key="s.label" :class="['flex justify-between text-xs', dark ? 'text-slate-400' : 'text-slate-500']">
              <span>{{ s.label }}</span>
              <span :class="['font-semibold', dark ? 'text-slate-300' : 'text-slate-700']">{{ s.value }}</span>
            </div>
          </div>
        </div>

        <!-- Quick suggestions -->
        <div class="card p-5">
          <h4 :class="['font-semibold text-sm mb-3', dark ? 'text-white' : 'text-slate-900']">💡 Tibbiy mavzular</h4>
          <div class="space-y-1.5">
            <button v-for="q in suggestedTopics" :key="q.text"
              @click="sendQuick(q.text)"
              :class="['w-full flex items-center gap-3 text-left p-2.5 rounded-xl transition-all border', dark ? 'border-slate-800 hover:border-slate-700 hover:bg-slate-800' : 'border-slate-100 hover:border-slate-200 hover:bg-slate-50']">
              <span class="text-lg flex-shrink-0">{{ q.icon }}</span>
              <span :class="['text-xs', dark ? 'text-slate-300' : 'text-slate-600']">{{ q.text }}</span>
            </button>
          </div>
        </div>

        <!-- Message count -->
        <div :class="['card p-4 text-center', dark ? '' : '']">
          <p :class="['text-3xl font-heading font-bold', dark ? 'text-white' : 'text-slate-900']">{{ messages.length }}</p>
          <p :class="['text-xs mt-1', dark ? 'text-slate-400' : 'text-slate-500']">Xabarlar soni</p>
          <div :class="['mt-3 h-1 rounded-full overflow-hidden', dark ? 'bg-slate-800' : 'bg-slate-100']">
            <div class="h-full rounded-full transition-all duration-500" :style="`width:${Math.min((messages.length/40)*100,100)}%; background:linear-gradient(90deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`"></div>
          </div>
          <p :class="['text-[10px] mt-1', dark ? 'text-slate-600' : 'text-slate-400']">{{ messages.length }}/40 (sessiya limiti)</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, reactive } from 'vue'
import { Bot, Send, RotateCcw, AlertCircle, Cpu } from 'lucide-vue-next'
import api from '@/composables/useApi'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore }  from '@/stores/auth'

const theme = useThemeStore()
const auth  = useAuthStore()
const dark  = computed(() => theme.isDark)
const userInitial = computed(() => (auth.user?.name || 'A')[0].toUpperCase())


const messages  = ref([])
const inputText = ref('')
const typing    = ref(false)
const error     = ref('')
const messagesEl = ref(null)
const inputEl   = ref(null)

const modelStats = [
  { label: 'Provider',    value: 'Backend LLM' },
  { label: 'Til',         value: "O'zbek" },
  { label: 'Temperature', value: '0.7' },
  { label: 'Max tokens',  value: '1024' },
]

const quickQuestions = [
  "Qon bosimi nima?",
  "Diabet turlari",
  "Og'riqsizlantirish usullari",
  "Yurak kasalliklari belgilari",
]

const suggestedTopics = [
  { icon: '🩺', text: 'Gipertenziya davolash protokoli' },
  { icon: '💊', text: 'Antibiotiklar buyurish qoidalari' },
  { icon: '🧪', text: 'Qon tahlili natijalarini talqin qilish' },
  { icon: '🫀', text: 'Yurak elektrokardioqrafiyasi' },
  { icon: '🧠', text: 'Nevrologik kasalliklar belgilari' },
  { icon: '👶', text: 'Bolalar emlanish jadvali' },
]

function now() {
  return new Date().toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit' })
}

function autoResize(e) {
  e.target.style.height = 'auto'
  e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px'
}

async function send() {
  const text = inputText.value.trim()
  if (!text || typing.value) return
  error.value = ''

  messages.value.push({ id: Date.now(), role: 'user', content: text, time: now() })
  inputText.value = ''
  if (inputEl.value) { inputEl.value.style.height = 'auto' }

  await nextTick()
  scrollBottom()
  typing.value = true

  // Oxirgi 10 ta xabar kontekst sifatida (joriy savolsiz) yuboriladi
  const history = messages.value.slice(-11, -1).map(m => ({ role: m.role, content: m.content }))

  try {
    const { data } = await api.post('/ai/chat', { message: text, history })
    const content = data.response || 'Javob olinmadi.'
    messages.value.push({ id: Date.now() + 1, role: 'assistant', content, time: now() })

  } catch (e) {
    console.error('AI chat error:', e)
    error.value = `Xatolik: ${e.response?.data?.detail || e.message}. Iltimos qayta urinib ko'ring.`
    messages.value.push({
      id: Date.now() + 1, role: 'assistant',
      content: '⚠️ Kechirasiz, hozirda javob bera olmayapman. Iltimos qayta urinib ko\'ring.',
      time: now()
    })
  } finally {
    typing.value = false
    await nextTick()
    scrollBottom()
  }
}

function sendQuick(text) {
  inputText.value = text
  send()
}

function clearChat() {
  messages.value = []
  error.value = ''
}

function scrollBottom() {
  if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
}
</script>