<template>
  <div :class="['flex h-[calc(100vh-112px)] rounded-2xl overflow-hidden border', dark ? 'border-slate-800' : 'border-slate-200']">

    <!-- ═══════════════════ SIDEBAR: Rooms ══════════════════════════════════ -->
    <div :class="['w-72 flex-shrink-0 flex flex-col border-r', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
      <!-- Header -->
      <div :class="['px-4 py-4 border-b', dark ? 'border-slate-800' : 'border-slate-100']">
        <h2 :class="['font-heading font-bold text-lg', dark ? 'text-white' : 'text-slate-900']">Chat</h2>
        <div class="relative mt-3">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input v-model="roomSearch" :class="['w-full pl-8 pr-3 py-2 rounded-xl text-sm border outline-none transition-colors', dark ? 'bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 focus:border-cyan-500' : 'bg-slate-50 border-slate-200 text-slate-900 focus:border-cyan-400']" placeholder="Qidirish..." />
        </div>
      </div>

      <!-- Room list -->
      <div class="flex-1 overflow-y-auto py-2">
        <div v-for="room in filteredRooms" :key="room.id"
          @click="selectRoom(room)"
          :class="['flex items-center gap-3 px-3 py-3 mx-2 rounded-xl cursor-pointer transition-all',
            activeRoom?.id === room.id
              ? dark ? 'bg-cyan-500/15 border border-cyan-500/30' : 'bg-cyan-50 border border-cyan-200'
              : dark ? 'hover:bg-slate-800' : 'hover:bg-slate-50']">
          <!-- Avatar -->
          <div class="relative flex-shrink-0">
            <div v-if="room.type === 'group'" :class="['w-11 h-11 rounded-xl flex items-center justify-center text-lg', dark ? 'bg-slate-800' : 'bg-slate-100']">
              {{ room.emoji || '💬' }}
            </div>
            <div v-else :class="['w-11 h-11 rounded-xl flex items-center justify-center text-sm font-bold text-white', avatarBg(room.name)]">
              {{ room.name[0] }}
            </div>
            <span v-if="room.online" class="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-400 rounded-full border-2" :class="dark ? 'border-slate-900' : 'border-white'"></span>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-1">
              <p :class="['text-sm font-semibold truncate', dark ? 'text-white' : 'text-slate-900']">{{ room.name }}</p>
              <span :class="['text-[10px] flex-shrink-0', dark ? 'text-slate-500' : 'text-slate-400']">{{ room.lastTime }}</span>
            </div>
            <p :class="['text-xs truncate mt-0.5', dark ? 'text-slate-400' : 'text-slate-500']">{{ room.lastMsg }}</p>
          </div>
          <span v-if="room.unread" class="w-5 h-5 rounded-full bg-cyan-500 text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0">{{ room.unread }}</span>
        </div>
      </div>

      <!-- Online staff -->
      <div :class="['border-t p-3', dark ? 'border-slate-800' : 'border-slate-100']">
        <p :class="['text-[10px] uppercase tracking-wider font-semibold mb-2 px-1', dark ? 'text-slate-500' : 'text-slate-400']">Online xodimlar</p>
        <div class="flex gap-2 flex-wrap">
          <div v-for="u in onlineUsers" :key="u.name" :title="u.name"
            :class="['relative w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white cursor-pointer', avatarBg(u.name)]">
            {{ u.name[0] }}
            <span class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 rounded-full border-2" :class="dark ? 'border-slate-900' : 'border-white'"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══════════════════ MAIN: Messages ══════════════════════════════════ -->
    <div class="flex-1 flex flex-col overflow-hidden" :class="dark ? 'bg-slate-950' : 'bg-slate-50'">
      <div v-if="!activeRoom" class="flex-1 flex flex-col items-center justify-center gap-3">
        <MessageSquare :class="['w-16 h-16', dark ? 'text-slate-700' : 'text-slate-300']" />
        <p :class="['text-sm font-medium', dark ? 'text-slate-500' : 'text-slate-400']">Chat tanlang</p>
      </div>

      <template v-else>
        <!-- Chat header -->
        <div :class="['flex items-center justify-between px-5 py-3.5 border-b flex-shrink-0', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
          <div class="flex items-center gap-3">
            <div :class="['w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold text-white', activeRoom.type === 'group' ? (dark ? 'bg-slate-700 text-xl' : 'bg-slate-200 text-xl') : avatarBg(activeRoom.name)]">
              {{ activeRoom.type === 'group' ? activeRoom.emoji : activeRoom.name[0] }}
            </div>
            <div>
              <p :class="['font-semibold text-sm', dark ? 'text-white' : 'text-slate-900']">{{ activeRoom.name }}</p>
              <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">{{ activeRoom.type === 'group' ? `${activeRoom.members} a'zo` : activeRoom.online ? 'Online' : 'Offline' }}</p>
            </div>
          </div>
          <div class="flex gap-1">
            <button :class="['p-2 rounded-xl transition-colors', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><Phone class="w-4 h-4" /></button>
            <button :class="['p-2 rounded-xl transition-colors', dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><MoreVertical class="w-4 h-4" /></button>
          </div>
        </div>

        <!-- Messages -->
        <div ref="msgContainer" class="flex-1 overflow-y-auto p-4 space-y-2">
          <template v-for="(msg, i) in roomMessages" :key="msg.id">
            <!-- Date separator -->
            <div v-if="isNewDay(i)" class="flex items-center gap-3 my-3">
              <div :class="['flex-1 h-px', dark ? 'bg-slate-800' : 'bg-slate-200']"></div>
              <span :class="['text-[11px] font-medium px-3 py-1 rounded-full', dark ? 'bg-slate-800 text-slate-400' : 'bg-slate-100 text-slate-500']">{{ formatDate(msg.time) }}</span>
              <div :class="['flex-1 h-px', dark ? 'bg-slate-800' : 'bg-slate-200']"></div>
            </div>

            <div :class="['flex gap-2.5 group', msg.mine ? 'flex-row-reverse' : '']">
              <!-- Avatar -->
              <div v-if="!msg.mine" :class="['w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0 mt-auto', avatarBg(msg.sender)]">
                {{ msg.sender[0] }}
              </div>

              <div :class="['max-w-sm lg:max-w-md', msg.mine ? 'items-end' : 'items-start', 'flex flex-col gap-1']">
                <p v-if="!msg.mine" :class="['text-[11px] font-semibold px-1', dark ? 'text-cyan-400' : 'text-cyan-600']">{{ msg.sender }}</p>

                <!-- Sticker -->
                <div v-if="msg.type === 'sticker'" class="text-5xl leading-none select-none">{{ msg.content }}</div>

                <!-- File -->
                <div v-else-if="msg.type === 'file'"
                  :class="['flex items-center gap-3 p-3 rounded-2xl border', msg.mine ? 'rounded-tr-sm' : 'rounded-tl-sm', dark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200']">
                  <div :class="['w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', dark ? 'bg-slate-700' : 'bg-slate-100']">
                    <FileIcon class="w-5 h-5 text-cyan-500" />
                  </div>
                  <div>
                    <p :class="['text-sm font-medium', dark ? 'text-slate-200' : 'text-slate-800']">{{ msg.content }}</p>
                    <p :class="['text-xs', dark ? 'text-slate-500' : 'text-slate-400']">{{ msg.fileSize }}</p>
                  </div>
                  <button :class="['p-1.5 rounded-lg ml-2', dark ? 'text-slate-400 hover:bg-slate-700' : 'text-slate-500 hover:bg-slate-100']"><Download class="w-3.5 h-3.5" /></button>
                </div>

                <!-- Text -->
                <div v-else
                  :class="['relative px-4 py-2.5 rounded-2xl text-sm leading-relaxed',
                    msg.mine
                      ? 'bg-gradient-to-br from-cyan-500 to-blue-600 text-white rounded-tr-sm'
                      : dark ? 'bg-slate-800 text-slate-100 rounded-tl-sm' : 'bg-white text-slate-800 rounded-tl-sm shadow-sm border border-slate-100']">
                  <span v-if="msg.edited" :class="['absolute -top-4 text-[10px]', dark ? 'text-slate-500' : 'text-slate-400']">tahrirlangan</span>
                  {{ msg.content }}
                </div>

                <div class="flex items-center gap-2">
                  <span :class="['text-[10px]', dark ? 'text-slate-600' : 'text-slate-400']">{{ formatTime(msg.time) }}</span>
                  <span v-if="msg.mine" :class="['text-[10px]', msg.read ? 'text-cyan-500' : dark ? 'text-slate-600' : 'text-slate-400']">{{ msg.read ? '✓✓' : '✓' }}</span>
                </div>
              </div>

              <!-- Actions (hover) -->
              <div :class="['flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity mt-auto mb-5', msg.mine ? 'flex-row-reverse' : '']">
                <button v-if="msg.mine && msg.type === 'text'" @click="startEdit(msg)" :class="['p-1 rounded-lg text-xs transition-colors', dark ? 'text-slate-500 hover:bg-slate-800 hover:text-slate-300' : 'text-slate-400 hover:bg-slate-100']"><Pencil class="w-3 h-3" /></button>
                <button @click="deleteMsg(msg.id)" :class="['p-1 rounded-lg text-xs transition-colors', dark ? 'text-slate-500 hover:bg-slate-800 hover:text-red-400' : 'text-slate-400 hover:bg-slate-100 hover:text-red-500']"><Trash2 class="w-3 h-3" /></button>
              </div>
            </div>
          </template>

          <!-- Typing indicator -->
          <div v-if="someoneTyping" class="flex items-center gap-2 pl-10">
            <div :class="['flex gap-1 px-4 py-3 rounded-2xl rounded-tl-sm', dark ? 'bg-slate-800' : 'bg-white shadow-sm border border-slate-100']">
              <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style="animation-delay:0ms"></span>
              <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style="animation-delay:150ms"></span>
              <span class="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" style="animation-delay:300ms"></span>
            </div>
          </div>
        </div>

        <!-- Edit banner -->
        <Transition name="slide-up">
          <div v-if="editingMsg" :class="['flex items-center gap-3 px-4 py-2.5 border-t', dark ? 'bg-slate-900 border-slate-800' : 'bg-blue-50 border-blue-100']">
            <Pencil class="w-4 h-4 text-blue-500 flex-shrink-0" />
            <div class="flex-1 min-w-0">
              <p class="text-xs font-semibold text-blue-500">Tahrirlash</p>
              <p :class="['text-xs truncate', dark ? 'text-slate-400' : 'text-slate-600']">{{ editingMsg.content }}</p>
            </div>
            <button @click="cancelEdit" :class="['p-1 rounded', dark ? 'text-slate-400 hover:text-white' : 'text-slate-500']"><X class="w-4 h-4" /></button>
          </div>
        </Transition>

        <!-- Sticker panel -->
        <Transition name="slide-up">
          <div v-if="showStickers" :class="['border-t p-3 grid grid-cols-8 gap-1.5', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
            <button v-for="s in stickers" :key="s" @click="sendSticker(s)" class="text-2xl hover:scale-125 transition-transform leading-none py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">{{ s }}</button>
          </div>
        </Transition>

        <!-- Input bar -->
        <div :class="['flex items-end gap-2 px-4 py-3 border-t flex-shrink-0', dark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
          <!-- Attach file -->
          <button @click="fileInput?.click()" :class="['p-2.5 rounded-xl transition-colors flex-shrink-0', dark ? 'text-slate-400 hover:bg-slate-800 hover:text-white' : 'text-slate-500 hover:bg-slate-100']">
            <Paperclip class="w-5 h-5" />
          </button>
          <input ref="fileInput" type="file" multiple class="hidden" @change="onFileSend" />

          <!-- Stickers -->
          <button @click="showStickers = !showStickers" :class="['p-2.5 rounded-xl transition-colors flex-shrink-0 text-xl leading-none', showStickers ? 'bg-cyan-500/10 text-cyan-500' : dark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']">😊</button>

          <!-- Text input -->
          <div class="flex-1">
            <textarea
              ref="textInput"
              v-model="inputText"
              @keydown.enter.exact.prevent="sendMessage"
              @keydown.enter.shift.exact="inputText += '\n'"
              @input="autoResize"
              :class="['w-full resize-none rounded-xl border px-3 py-2.5 text-sm outline-none transition-colors', dark ? 'bg-slate-800 border-slate-700 text-white placeholder:text-slate-500 focus:border-cyan-500' : 'bg-slate-50 border-slate-200 text-slate-900 focus:border-cyan-400']"
              placeholder="Xabar yozing... (Enter — yuborish, Shift+Enter — yangi qator)"
              rows="1"
              style="max-height:120px"
            ></textarea>
          </div>

          <!-- Send -->
          <button
            @click="sendMessage"
            :disabled="!inputText.trim()"
            :class="['p-2.5 rounded-xl transition-all flex-shrink-0',
              inputText.trim()
                ? 'bg-gradient-to-br from-cyan-500 to-blue-600 text-white shadow-sm hover:shadow-md'
                : dark ? 'bg-slate-800 text-slate-600' : 'bg-slate-100 text-slate-300']">
            <Send class="w-5 h-5" />
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { Search, MessageSquare, Phone, MoreVertical, Pencil, Trash2, Send, Paperclip, Download, X, FileIcon } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'

const theme = useThemeStore()
const auth  = useAuthStore()
const dark  = computed(() => theme.isDark)

const ME = computed(() => auth.user?.name || 'Admin')

const gradients = ['bg-gradient-to-br from-cyan-500 to-blue-600','bg-gradient-to-br from-violet-500 to-purple-600','bg-gradient-to-br from-emerald-500 to-teal-600','bg-gradient-to-br from-orange-500 to-red-500','bg-gradient-to-br from-pink-500 to-rose-500','bg-gradient-to-br from-amber-500 to-yellow-500']
function avatarBg(n) { return gradients[(n?.charCodeAt(0)||0) % gradients.length] }

const stickers = ['👍','❤️','😂','😮','😢','🔥','🎉','💊','🏥','👨‍⚕️','👩‍⚕️','💉','🩺','📋','✅','⚠️','💯','🙏','😎','🤝','👏','🎯','⭐','💪','🚀','🌟','😴','🤒']

const rooms = ref([
  { id: 'g1', name: 'Umumiy chat', type: 'group', emoji: '🏥', members: 12, lastMsg: 'Bugun qabul 3 soatga', lastTime: '09:41', unread: 3, online: true },
  { id: 'g2', name: 'Shifokorlar', type: 'group', emoji: '👨‍⚕️', members: 5, lastMsg: 'Yangi protokol yuborildi', lastTime: '08:30', unread: 1, online: true },
  { id: 'g3', name: 'Hamshiralar', type: 'group', emoji: '💉', members: 4, lastMsg: 'Stol navbatini ko\'ring', lastTime: 'Kecha', unread: 0, online: false },
  { id: 'p1', name: 'Dr. Rustamov',  type: 'private', lastMsg: 'Rahmat!', lastTime: '10:05', unread: 0, online: true },
  { id: 'p2', name: 'Dr. Karimov',   type: 'private', lastMsg: 'Bemor ma\'lumotlarini jo\'nating', lastTime: 'Kecha', unread: 2, online: false },
  { id: 'p3', name: 'Nilufar Azimova', type: 'private', lastMsg: "Qabul ro'yxatini tuzaylik", lastTime: 'Kecha', unread: 0, online: true },
])

const onlineUsers = ref([
  { name: 'Dr. Rustamov' }, { name: 'Nilufar Azimova' }, { name: 'Admin' }, { name: 'Malika Yusupova' }
])

const messages = ref({
  g1: [
    { id: 1, sender: 'Dr. Rustamov', content: 'Salom hammaga! Bugun qabul soat 9 da boshlanadi.', time: new Date(Date.now()-7200000), type:'text', mine:false, read:true },
    { id: 2, sender: 'Nilufar Azimova', content: 'Tushunildi, rahmat!', time: new Date(Date.now()-7000000), type:'text', mine:false, read:true },
    { id: 3, sender: ME.value, content: 'Yangi bemorlar ro\'yxatini yukladim.', time: new Date(Date.now()-3600000), type:'text', mine:true, read:true },
    { id: 4, sender: 'Dr. Karimov', content: '👍', time: new Date(Date.now()-3500000), type:'sticker', mine:false, read:true },
    { id: 5, sender: 'Dr. Rustamov', content: 'Bugun qabul 3 soatga', time: new Date(Date.now()-600000), type:'text', mine:false, read:false },
  ],
  g2: [
    { id: 1, sender: 'Dr. Karimov', content: 'Yangi protokol yuborildi', time: new Date(Date.now()-5400000), type:'text', mine:false, read:true },
    { id: 2, sender: ME.value, content: "Ko'rdim, o'rganib chiqaman.", time: new Date(Date.now()-5000000), type:'text', mine:true, read:true },
  ],
  g3: [
    { id: 1, sender: 'Malika Yusupova', content: 'Stol navbatini ko\'ring', time: new Date(Date.now()-86400000), type:'text', mine:false, read:true },
  ],
  p1: [
    { id: 1, sender: 'Dr. Rustamov', content: 'Salom! Vaziyat yaxshimi?', time: new Date(Date.now()-1800000), type:'text', mine:false, read:true },
    { id: 2, sender: ME.value, content: 'Yaxshi, sog\' bo\'ling!', time: new Date(Date.now()-1700000), type:'text', mine:true, read:true },
    { id: 3, sender: 'Dr. Rustamov', content: 'Rahmat!', time: new Date(Date.now()-600000), type:'text', mine:false, read:true },
  ],
  p2: [
    { id: 1, sender: 'Dr. Karimov', content: "Bemor ma'lumotlarini jo'nating", time: new Date(Date.now()-90000000), type:'text', mine:false, read:false },
    { id: 2, sender: 'Dr. Karimov', content: 'protocol_v2.pdf', time: new Date(Date.now()-80000000), type:'file', fileSize:'2.4 MB', mine:false, read:false },
  ],
  p3: [
    { id: 1, sender: ME.value, content: "Qabul ro'yxatini tuzaylik", time: new Date(Date.now()-86400000), type:'text', mine:true, read:true },
    { id: 2, sender: 'Nilufar Azimova', content: 'Maylida!', time: new Date(Date.now()-86000000), type:'text', mine:false, read:true },
  ],
})

const activeRoom   = ref(null)
const roomSearch   = ref('')
const inputText    = ref('')
const showStickers = ref(false)
const editingMsg   = ref(null)
const someoneTyping = ref(false)
const msgContainer = ref(null)
const fileInput    = ref(null)
const textInput    = ref(null)

const filteredRooms = computed(() => {
  const q = roomSearch.value.toLowerCase()
  if (!q) return rooms.value
  return rooms.value.filter(r => r.name.toLowerCase().includes(q))
})
const roomMessages = computed(() => activeRoom.value ? (messages.value[activeRoom.value.id] || []) : [])

function selectRoom(room) {
  activeRoom.value = room
  room.unread = 0
  showStickers.value = false
  nextTick(scrollBottom)
  // Simulate someone typing
  setTimeout(() => { someoneTyping.value = true; setTimeout(() => someoneTyping.value = false, 3000) }, 2000)
}

function scrollBottom() {
  if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight
}

function formatTime(d) { return d instanceof Date ? d.toLocaleTimeString('uz-UZ', { hour:'2-digit', minute:'2-digit' }) : d }
function formatDate(d) {
  if (!(d instanceof Date)) return d
  const today = new Date()
  const diff = Math.floor((today - d) / 86400000)
  if (diff === 0) return 'Bugun'
  if (diff === 1) return 'Kecha'
  return d.toLocaleDateString('uz-UZ')
}
function isNewDay(i) {
  if (i === 0) return true
  const msgs = roomMessages.value
  const a = msgs[i-1]?.time
  const b = msgs[i]?.time
  if (!a || !b || !(a instanceof Date) || !(b instanceof Date)) return false
  return a.toDateString() !== b.toDateString()
}

function sendMessage() {
  if (!inputText.value.trim() || !activeRoom.value) return
  if (editingMsg.value) {
    editingMsg.value.content = inputText.value.trim()
    editingMsg.value.edited  = true
    cancelEdit()
    return
  }
  const list = messages.value[activeRoom.value.id]
  list.push({
    id: Date.now(), sender: ME.value, content: inputText.value.trim(),
    time: new Date(), type: 'text', mine: true, read: false
  })
  // Update room last message
  const room = rooms.value.find(r => r.id === activeRoom.value.id)
  if (room) { room.lastMsg = inputText.value.trim(); room.lastTime = formatTime(new Date()) }
  inputText.value = ''
  showStickers.value = false
  nextTick(scrollBottom)
  // Simulate reply
  simulateReply()
}

function simulateReply() {
  if (activeRoom.value?.type !== 'private') return
  const replies = ['Tushunildi!', 'Yaxshi, ko\'rib chiqaman.', '👍', 'Rahmat!', '✅ Amalga oshirildi.']
  const delay = 1500 + Math.random() * 2000
  someoneTyping.value = true
  setTimeout(() => {
    someoneTyping.value = false
    const list = messages.value[activeRoom.value.id]
    list.push({ id: Date.now(), sender: activeRoom.value.name, content: replies[Math.floor(Math.random()*replies.length)], time: new Date(), type: 'text', mine: false, read: false })
    nextTick(scrollBottom)
  }, delay)
}

function sendSticker(s) {
  if (!activeRoom.value) return
  const list = messages.value[activeRoom.value.id]
  list.push({ id: Date.now(), sender: ME.value, content: s, time: new Date(), type: 'sticker', mine: true, read: false })
  showStickers.value = false
  nextTick(scrollBottom)
}

function onFileSend(e) {
  if (!activeRoom.value) return
  const list = messages.value[activeRoom.value.id]
  Array.from(e.target.files).forEach(f => {
    list.push({
      id: Date.now() + Math.random(), sender: ME.value, content: f.name,
      fileSize: (f.size / 1024 / 1024).toFixed(1) + ' MB',
      time: new Date(), type: 'file', mine: true, read: false
    })
  })
  e.target.value = ''
  nextTick(scrollBottom)
}

function startEdit(msg) {
  editingMsg.value = msg
  inputText.value  = msg.content
  textInput.value?.focus()
}
function cancelEdit() { editingMsg.value = null; inputText.value = '' }

function deleteMsg(id) {
  if (!activeRoom.value) return
  const list = messages.value[activeRoom.value.id]
  const i = list.findIndex(m => m.id === id)
  if (i >= 0) list.splice(i, 1)
}

function autoResize(e) {
  e.target.style.height = 'auto'
  e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
}

onMounted(() => selectRoom(rooms.value[0]))
</script>

<style scoped>
.slide-up-enter-active { transition: all .2s ease-out; }
.slide-up-leave-active { transition: all .15s ease-in; }
.slide-up-enter-from { opacity: 0; transform: translateY(8px); }
.slide-up-leave-to   { opacity: 0; transform: translateY(8px); }
</style>