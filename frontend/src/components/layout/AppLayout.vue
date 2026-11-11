<template>
  <div :class="['flex h-screen overflow-hidden transition-colors duration-300', isDark ? 'bg-slate-950' : 'bg-slate-50']">

    <!-- Theme effect overlay (subtle, on theme change) -->
    <Transition name="effect-fade">
      <div v-if="showEffect" class="fixed inset-0 pointer-events-none z-[200] overflow-hidden">
        <!-- WAVE (cyan) -->
        <template v-if="currentTheme.effect === 'wave'">
          <div v-for="i in 6" :key="i" class="absolute h-1 rounded-full opacity-60"
            :style="{ left:0, right:0, top: `${15*i}%`, background: `rgb(var(--c-primary))`, animation: `wave 0.8s ease ${i*0.08}s both`, transform:'scaleX(0)' }"></div>
        </template>
        <!-- STARS (violet) -->
        <template v-if="currentTheme.effect === 'stars'">
          <div v-for="i in 20" :key="i" class="absolute w-1.5 h-1.5 rounded-full"
            :style="{ left:`${Math.random()*100}%`, top:`${Math.random()*100}%`, background:`rgb(var(--c-primary))`, animation:`starFloat ${0.5+Math.random()*0.6}s ease forwards ${Math.random()*0.4}s` }"></div>
        </template>
        <!-- LEAVES (emerald) -->
        <template v-if="currentTheme.effect === 'leaves'">
          <div v-for="i in 14" :key="i" class="absolute text-2xl"
            :style="{ left:`${Math.random()*100}%`, top:`${Math.random()*100}%`, animation:`leafDrift ${0.6+Math.random()*0.5}s ease forwards ${Math.random()*0.3}s` }">🌿</div>
        </template>
        <!-- PETALS (rose) -->
        <template v-if="currentTheme.effect === 'petals'">
          <div v-for="i in 16" :key="i" class="absolute text-xl"
            :style="{ left:`${Math.random()*100}%`, top:`${Math.random()*80}%`, animation:`petalFall ${0.5+Math.random()*0.7}s ease forwards ${Math.random()*0.4}s` }">🌸</div>
        </template>
        <!-- RAYS (amber) -->
        <template v-if="currentTheme.effect === 'rays'">
          <div v-for="i in 8" :key="i" class="absolute top-0 bottom-0 w-16 opacity-0"
            :style="{ left:`${12.5*i}%`, background:`linear-gradient(to bottom, transparent, rgb(var(--c-primary)), transparent)`, animation:`rayPulse 0.8s ease ${i*0.07}s both` }"></div>
        </template>
        <!-- GRID (slate) -->
        <template v-if="currentTheme.effect === 'grid'">
          <div class="absolute inset-0 opacity-20"
            :style="{ background:`repeating-linear-gradient(0deg, rgb(var(--c-primary)) 0px, transparent 1px, transparent 19px, rgb(var(--c-primary)) 20px), repeating-linear-gradient(90deg, rgb(var(--c-primary)) 0px, transparent 1px, transparent 19px, rgb(var(--c-primary)) 20px)`, animation:`gridMove 0.5s linear` }"></div>
        </template>
      </div>
    </Transition>

    <!-- ════ SIDEBAR ════════════════════════════════════════════════════════ -->
    <aside :class="[
      'sidebar border-r transition-colors duration-300',
      isDark ? 'bg-slate-900 border-slate-800 sidebar-dark' : 'bg-white border-slate-200 sidebar-light',
      { collapsed: sidebarCollapsed }
    ]">
      <!-- Logo -->
      <div :class="['flex items-center gap-3 px-4 py-5 border-b', isDark ? 'border-slate-800' : 'border-slate-200', sidebarCollapsed ? 'justify-center' : '']">
        <div class="h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg"
          :style="`background: linear-gradient(135deg, rgb(var(--c-primary)), rgb(var(--c-secondary)))`">
          <span class="text-sm font-bold text-white font-heading">DC</span>
        </div>
        <Transition name="fade">
          <div v-if="!sidebarCollapsed">
            <h1 :class="['font-heading text-[15px] font-bold leading-none', isDark ? 'text-white' : 'text-slate-900']">Digital Clinic</h1>
            <p :class="['text-[11px] mt-0.5', isDark ? 'text-slate-500' : 'text-slate-400']">Healthcare Platform</p>
          </div>
        </Transition>
      </div>

      <!-- Nav -->
      <div class="flex-1 overflow-y-auto py-4 px-3">
        <div v-if="mainNav.length" class="mb-3">
          <p v-if="!sidebarCollapsed" :class="['px-3 text-[10px] uppercase tracking-widest font-semibold mb-2', isDark ? 'text-slate-600' : 'text-slate-400']">{{ lang.t('nav.main') }}</p>
          <nav class="space-y-0.5">
            <RouterLink v-for="item in mainNav" :key="item.to" :to="item.to"
              class="sidebar-link" :class="{ active: isActive(item.to, item.exact) }"
              :title="sidebarCollapsed ? lang.t(item.key) : ''">
              <component :is="item.icon" class="w-[18px] h-[18px] flex-shrink-0" />
              <Transition name="fade"><span v-if="!sidebarCollapsed">{{ lang.t(item.key) }}</span></Transition>
              <span v-if="item.to === '/chat' && !sidebarCollapsed && unreadMessages > 0"
                class="ml-auto text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center flex-shrink-0"
                :style="`background:rgb(var(--c-primary))`">{{ unreadMessages }}</span>
            </RouterLink>
          </nav>
        </div>
        <div v-if="systemNav.length" :class="['pt-3 border-t', isDark ? 'border-slate-800' : 'border-slate-200']">
          <p v-if="!sidebarCollapsed" :class="['px-3 text-[10px] uppercase tracking-widest font-semibold mb-2', isDark ? 'text-slate-600' : 'text-slate-400']">{{ lang.t('nav.system') }}</p>
          <nav class="space-y-0.5">
            <RouterLink v-for="item in systemNav" :key="item.to" :to="item.to"
              class="sidebar-link" :class="{ active: isActive(item.to) }"
              :title="sidebarCollapsed ? lang.t(item.key) : ''">
              <component :is="item.icon" class="w-[18px] h-[18px] flex-shrink-0" />
              <Transition name="fade"><span v-if="!sidebarCollapsed">{{ lang.t(item.key) }}</span></Transition>
            </RouterLink>
          </nav>
        </div>
      </div>

      <!-- User block -->
      <div :class="['border-t p-3', isDark ? 'border-slate-800' : 'border-slate-200', sidebarCollapsed ? 'flex justify-center' : '']">
        <div :class="['flex items-center gap-3 rounded-xl px-2 py-2 cursor-pointer transition-all group', isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100', sidebarCollapsed ? 'justify-center' : '']" @click="openUserEdit">
          <div class="relative flex-shrink-0">
            <div class="w-8 h-8 rounded-full overflow-hidden">
              <img v-if="userAvatar" :src="userAvatar" class="w-full h-full object-cover" />
              <div v-else class="w-full h-full flex items-center justify-center" :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
                <span class="text-xs font-bold text-white">{{ userInitial }}</span>
              </div>
            </div>
            <span class="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 bg-emerald-400 rounded-full border-2" :class="isDark ? 'border-slate-900' : 'border-white'"></span>
          </div>
          <Transition name="fade">
            <div v-if="!sidebarCollapsed" class="min-w-0 flex-1">
              <p :class="['text-sm font-medium truncate', isDark ? 'text-white' : 'text-slate-900']">{{ auth.user?.name || 'Admin' }}</p>
              <p :class="['text-xs truncate', isDark ? 'text-slate-500' : 'text-slate-400']">{{ auth.user?.email || 'admin@clinic.uz' }}</p>
            </div>
          </Transition>
          <Transition name="fade">
            <Pencil v-if="!sidebarCollapsed" :class="['w-3.5 h-3.5 flex-shrink-0', isDark ? 'text-slate-600 group-hover:text-slate-400' : 'text-slate-400 group-hover:text-slate-600']" />
          </Transition>
        </div>
      </div>
    </aside>

    <!-- ════ MAIN ═══════════════════════════════════════════════════════════ -->
    <div class="flex flex-col flex-1 overflow-hidden"
      :style="{ marginLeft: sidebarCollapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-w)', transition: 'margin 0.3s ease' }">

      <!-- Topbar -->
      <header :class="['h-16 border-b flex items-center justify-between px-5 flex-shrink-0 z-40 transition-colors duration-300', isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
        <div class="flex items-center gap-2">
          <button :class="['p-2 rounded-xl transition-colors', isDark ? 'text-slate-400 hover:bg-slate-800 hover:text-white' : 'text-slate-500 hover:bg-slate-100']" @click="sidebarCollapsed = !sidebarCollapsed">
            <PanelLeft class="w-5 h-5" />
          </button>
          <h2 :class="['hidden md:block text-base font-semibold', isDark ? 'text-white' : 'text-slate-900']">{{ pageTitle }}</h2>
        </div>

        <div class="flex items-center gap-1.5">

          <!-- Dark/Light toggle -->
          <button @click="theme.toggle()" :class="['p-2 rounded-xl transition-all duration-200', isDark ? 'text-amber-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']">
            <Transition name="icon-flip" mode="out-in">
              <Sun v-if="isDark" key="sun" class="w-5 h-5" />
              <Moon v-else key="moon" class="w-5 h-5" />
            </Transition>
          </button>

          <!-- Theme picker button -->
          <div class="relative" ref="themeRef">
            <button @click="closeAll('theme')"
              :class="['flex items-center gap-1.5 p-2 rounded-xl transition-all', isDark ? 'text-slate-400 hover:bg-slate-800 hover:text-white' : 'text-slate-500 hover:bg-slate-100']"
              title="Tema tanlash">
              <Palette class="w-5 h-5" />
              <span class="w-3 h-3 rounded-full border-2 border-white shadow" :style="`background:rgb(var(--c-primary))`"></span>
            </button>
            <Transition name="dropdown">
              <div v-if="themeOpen" :class="['absolute right-0 top-[calc(100%+6px)] w-80 rounded-2xl shadow-2xl border z-50 overflow-hidden', isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200']">
                <div :class="['px-4 py-3 border-b', isDark ? 'border-slate-700' : 'border-slate-100']">
                  <p :class="['font-semibold text-sm', isDark ? 'text-white' : 'text-slate-900']">🎨 Tema tanlash</p>
                  <p :class="['text-xs mt-0.5', isDark ? 'text-slate-400' : 'text-slate-500']">Har bir tema o'ziga xos effekt beradi</p>
                </div>
                <div class="p-3 grid grid-cols-2 gap-2">
                  <button v-for="t in themeStore.themes" :key="t.id"
                    @click="selectTheme(t.id)"
                    :class="['relative overflow-hidden rounded-xl p-3 text-left transition-all border-2',
                      themeStore.themeId === t.id
                        ? 'border-transparent ring-2 ring-offset-1 scale-[1.02]'
                        : isDark ? 'border-slate-700 hover:border-slate-600 hover:scale-[1.01]' : 'border-slate-200 hover:border-slate-300 hover:scale-[1.01]']"
                    :style="themeStore.themeId === t.id ? `ring-color:rgb(var(--c-primary))` : ''">
                    <!-- gradient strip -->
                    <div class="h-8 rounded-lg mb-2 shadow-sm" :class="t.preview"></div>
                    <div class="flex items-center gap-1.5">
                      <span class="text-base leading-none">{{ t.emoji }}</span>
                      <div>
                        <p :class="['text-xs font-semibold', isDark ? 'text-slate-200' : 'text-slate-800']">{{ t.name }}</p>
                        <p :class="['text-[10px]', isDark ? 'text-slate-500' : 'text-slate-400']">{{ t.desc }}</p>
                      </div>
                    </div>
                    <!-- active tick -->
                    <div v-if="themeStore.themeId === t.id" class="absolute top-2 right-2 w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px] font-bold shadow"
                      :style="`background:rgb(var(--c-primary))`">✓</div>
                  </button>
                </div>
              </div>
            </Transition>
          </div>

          <!-- Language -->
          <div class="relative" ref="langRef">
            <button @click="closeAll('lang')" :class="['flex items-center gap-1.5 pl-2.5 pr-2 py-1.5 rounded-xl text-sm font-medium transition-all border', isDark ? 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700' : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50']">
              <Globe class="w-3.5 h-3.5" /><span class="text-[13px]">{{ lang.currentLang?.flag }}&thinsp;{{ lang.currentLang?.label }}</span>
              <ChevronDown :class="['w-3 h-3 transition-transform duration-200', langOpen ? 'rotate-180' : '']" />
            </button>
            <Transition name="dropdown">
              <div v-if="langOpen" :class="['absolute right-0 top-[calc(100%+6px)] w-44 rounded-2xl shadow-xl border z-50 overflow-hidden py-1', isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200']">
                <button v-for="l in lang.languages" :key="l.code" @click="selectLang(l.code)"
                  :class="['flex items-center gap-3 w-full px-4 py-2.5 text-sm text-left transition-colors', lang.current === l.code ? isDark ? 'text-slate-100 font-semibold' : 'text-slate-900 font-semibold bg-slate-50' : isDark ? 'text-slate-300 hover:bg-slate-700/60' : 'text-slate-700 hover:bg-slate-50']">
                  <span class="text-base">{{ l.flag }}</span><span>{{ l.label }}</span>
                  <Check v-if="lang.current === l.code" class="ml-auto w-3.5 h-3.5" :style="`color:rgb(var(--c-primary))`" />
                </button>
              </div>
            </Transition>
          </div>

          <!-- Notifications -->
          <div class="relative" ref="notifRef">
            <button @click="closeAll('notif')" :class="['relative p-2 rounded-xl transition-colors', isDark ? 'text-slate-400 hover:bg-slate-800 hover:text-white' : 'text-slate-500 hover:bg-slate-100']">
              <Bell class="w-5 h-5" />
              <span v-if="unreadNotifs" class="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1">{{ unreadNotifs }}</span>
            </button>
            <Transition name="dropdown">
              <div v-if="notifOpen" :class="['absolute right-0 top-[calc(100%+6px)] w-80 rounded-2xl shadow-xl border z-50 overflow-hidden', isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200']">
                <div :class="['flex items-center justify-between px-4 py-3 border-b', isDark ? 'border-slate-700' : 'border-slate-100']">
                  <span :class="['font-semibold text-sm', isDark ? 'text-white' : 'text-slate-900']">Bildirishnomalar</span>
                  <button @click="markAllRead" class="text-xs font-medium" :style="`color:rgb(var(--c-primary))`">Barchasini o'qi</button>
                </div>
                <div class="max-h-72 overflow-y-auto">
                  <div v-for="n in notifications" :key="n.id"
                    :class="['flex gap-3 px-4 py-3 cursor-pointer border-b last:border-b-0 transition-colors', !n.read ? isDark ? 'bg-white/3' : 'bg-slate-50/80' : '', isDark ? 'border-slate-700/50 hover:bg-slate-700/40' : 'border-slate-50 hover:bg-slate-50']"
                    @click="n.read = true">
                    <div :class="['w-8 h-8 rounded-xl flex items-center justify-center text-sm flex-shrink-0', n.bg]">{{ n.icon }}</div>
                    <div class="flex-1 min-w-0">
                      <p :class="['text-sm', isDark ? 'text-slate-200' : 'text-slate-800', !n.read ? 'font-medium' : '']">{{ n.text }}</p>
                      <p :class="['text-xs mt-0.5', isDark ? 'text-slate-500' : 'text-slate-400']">{{ n.time }}</p>
                    </div>
                    <div v-if="!n.read" class="w-2 h-2 rounded-full flex-shrink-0 mt-2" :style="`background:rgb(var(--c-primary))`"></div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <!-- User dropdown -->
          <div class="relative" ref="userRef">
            <button @click="closeAll('user')" class="flex items-center gap-2 pl-1 pr-2 py-1 rounded-xl transition-colors" :class="isDark ? 'hover:bg-slate-800' : 'hover:bg-slate-100'">
              <div class="h-8 w-8 rounded-full overflow-hidden flex-shrink-0 shadow-sm">
                <img v-if="userAvatar" :src="userAvatar" class="w-full h-full object-cover" />
                <div v-else class="w-full h-full flex items-center justify-center" :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
                  <span class="text-xs font-bold text-white">{{ userInitial }}</span>
                </div>
              </div>
              <div class="hidden sm:block text-left">
                <p :class="['text-sm font-medium leading-none', isDark ? 'text-white' : 'text-slate-900']">{{ auth.user?.name || 'Admin' }}</p>
                <p :class="['text-[11px] mt-0.5', isDark ? 'text-slate-500' : 'text-slate-400']">{{ auth.user?.role || 'Admin' }}</p>
              </div>
              <ChevronDown :class="['w-3.5 h-3.5 hidden sm:block transition-transform duration-200', isDark ? 'text-slate-500' : 'text-slate-400', userOpen ? 'rotate-180' : '']" />
            </button>
            <Transition name="dropdown">
              <div v-if="userOpen" :class="['absolute right-0 top-[calc(100%+6px)] w-52 rounded-2xl shadow-xl border z-50 overflow-hidden py-1', isDark ? 'bg-slate-800 border-slate-700' : 'bg-white border-slate-200']">
                <div :class="['px-4 py-3 border-b', isDark ? 'border-slate-700' : 'border-slate-100']">
                  <p :class="['text-sm font-semibold', isDark ? 'text-white' : 'text-slate-900']">{{ auth.user?.name || 'Admin' }}</p>
                  <p :class="['text-xs', isDark ? 'text-slate-400' : 'text-slate-500']">{{ auth.user?.email || 'admin@clinic.uz' }}</p>
                </div>
                <button @click="openUserEdit" :class="['flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-left transition-colors', isDark ? 'text-slate-300 hover:bg-slate-700' : 'text-slate-700 hover:bg-slate-50']">
                  <Pencil class="w-4 h-4" /> Profilni tahrirlash
                </button>
                <RouterLink v-if="auth.can('audit:read')" to="/security" @click="userOpen=false" :class="['flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors', isDark ? 'text-slate-300 hover:bg-slate-700' : 'text-slate-700 hover:bg-slate-50']">
                  <Shield class="w-4 h-4" /> Xavfsizlik
                </RouterLink>
                <div :class="['border-t my-1', isDark ? 'border-slate-700' : 'border-slate-100']"></div>
                <button @click="logout" :class="['flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-left text-red-500 transition-colors', isDark ? 'hover:bg-red-500/10' : 'hover:bg-red-50']">
                  <LogOut class="w-4 h-4" /> Chiqish
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </header>

      <main :class="['flex-1 overflow-y-auto p-6 transition-colors duration-300', isDark ? 'bg-slate-950' : 'bg-slate-50']">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>

    <!-- ════ USER EDIT MODAL ═══════════════════════════════════════════════ -->
    <Transition name="modal-fade">
      <div v-if="showUserEdit" class="modal-overlay" @click.self="showUserEdit = false">
        <div :class="['w-full max-w-md rounded-2xl shadow-2xl overflow-hidden animate-fade-in', isDark ? 'bg-slate-900 border border-slate-800' : 'bg-white']">
          <div :class="['flex items-center justify-between px-6 py-4 border-b', isDark ? 'border-slate-800' : 'border-slate-200']">
            <h3 :class="['font-heading font-semibold text-lg', isDark ? 'text-white' : 'text-slate-900']">Profilni tahrirlash</h3>
            <button @click="showUserEdit = false" :class="['p-1.5 rounded-lg', isDark ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-500 hover:bg-slate-100']"><X class="w-4 h-4" /></button>
          </div>
          <div class="p-6 space-y-5">
            <div class="flex flex-col items-center gap-3">
              <div class="relative group cursor-pointer" @click="avatarInput?.click()">
                <div class="w-24 h-24 rounded-2xl overflow-hidden shadow-lg" :style="`ring:4px solid rgb(var(--c-primary)/.3)`">
                  <img v-if="editForm.avatarPreview" :src="editForm.avatarPreview" class="w-full h-full object-cover" />
                  <div v-else class="w-full h-full flex items-center justify-center" :style="`background:linear-gradient(135deg,rgb(var(--c-primary)),rgb(var(--c-secondary)))`">
                    <span class="text-3xl font-bold text-white">{{ userInitial }}</span>
                  </div>
                </div>
                <div class="absolute inset-0 rounded-2xl bg-black/50 flex flex-col items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <Camera class="w-6 h-6 text-white" />
                </div>
              </div>
              <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="onAvatarChange" />
              <div class="flex gap-2">
                <button class="btn-secondary text-xs !px-3 !py-1.5" @click="avatarInput?.click()"><Camera class="w-3.5 h-3.5" />{{ editForm.avatarPreview ? 'Almashti' : "Surat qo'sh" }}</button>
                <button v-if="editForm.avatarPreview" class="btn-ghost text-xs !px-3 !py-1.5 text-red-500" @click="editForm.avatarPreview = ''"><Trash2 class="w-3.5 h-3.5" /></button>
              </div>
            </div>
            <div class="space-y-3">
              <div><label :class="lbl">To'liq ism</label><input v-model="editForm.name" class="input" /></div>
              <div><label :class="lbl">Email</label><input v-model="editForm.email" type="email" class="input" /></div>
              <div :class="['border-t pt-3', isDark ? 'border-slate-800' : 'border-slate-100']">
                <label :class="lbl">Yangi parol <span class="font-normal text-slate-400">(ixtiyoriy)</span></label>
                <input v-model="editForm.newPassword" type="password" class="input" placeholder="••••••••" />
              </div>
            </div>
            <div class="flex gap-3 pt-1">
              <button class="btn-secondary flex-1" @click="showUserEdit = false">Bekor</button>
              <button class="btn-primary flex-1" @click="saveUser"><Check class="w-4 h-4" />Saqlash</button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onUnmounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore }     from '@/stores/auth'
import { useLanguageStore } from '@/stores/language'
import { useThemeStore }    from '@/stores/theme'
import {
  LayoutDashboard, Users, Calendar, FileText, DollarSign, BarChart3, Bot,
  FileBarChart, UserCog, CreditCard, Shield, Settings, Bell, PanelLeft,
  Globe, ChevronDown, Check, Sun, Moon, Pencil, LogOut, X, Camera, Trash2,
  MessageSquare, Palette, FlaskConical
} from 'lucide-vue-next'

const auth        = useAuthStore()
const lang        = useLanguageStore()
const theme       = useThemeStore()
const themeStore  = useThemeStore()
const route       = useRoute()
const router      = useRouter()

const isDark        = computed(() => theme.isDark)
const currentTheme  = computed(() => theme.currentTheme)
const sidebarCollapsed = ref(false)
const unreadMessages   = ref(3)
const showEffect       = ref(false)

// Dropdowns
const langOpen  = ref(false)
const notifOpen = ref(false)
const userOpen  = ref(false)
const themeOpen = ref(false)
const langRef   = ref(null)
const notifRef  = ref(null)
const userRef   = ref(null)
const themeRef  = ref(null)

function closeAll(open = null) {
  langOpen.value  = open === 'lang'  ? !langOpen.value  : false
  notifOpen.value = open === 'notif' ? !notifOpen.value : false
  userOpen.value  = open === 'user'  ? !userOpen.value  : false
  themeOpen.value = open === 'theme' ? !themeOpen.value : false
}
function handleClickOutside(e) {
  if (langRef.value  && !langRef.value.contains(e.target))  langOpen.value  = false
  if (notifRef.value && !notifRef.value.contains(e.target)) notifOpen.value = false
  if (userRef.value  && !userRef.value.contains(e.target))  userOpen.value  = false
  if (themeRef.value && !themeRef.value.contains(e.target)) themeOpen.value = false
}
onMounted(() => document.addEventListener('mousedown', handleClickOutside))
onUnmounted(() => document.removeEventListener('mousedown', handleClickOutside))

function selectTheme(id) {
  theme.setTheme(id)
  themeOpen.value = false
  // Show effect
  showEffect.value = false
  setTimeout(() => { showEffect.value = true; setTimeout(() => showEffect.value = false, 900) }, 50)
}
function selectLang(code) { lang.setLanguage(code); langOpen.value = false }

// Notifications
const notifications = ref([
  { id: 1, icon: '👤', bg: 'bg-blue-100',    text: "Yangi bemor qo'shildi",    time: '5 daqiqa oldin',  read: false },
  { id: 2, icon: '📅', bg: 'bg-purple-100',  text: 'Yangi qabul yaratildi',    time: '20 daqiqa oldin', read: false },
  { id: 3, icon: '💰', bg: 'bg-emerald-100', text: "To'lov qabul qilindi",     time: '1 soat oldin',    read: true  },
])
const unreadNotifs = computed(() => notifications.value.filter(n => !n.read).length)
function markAllRead() { notifications.value.forEach(n => n.read = true) }

// User
const userAvatar   = ref(localStorage.getItem('userAvatar') || '')
const showUserEdit = ref(false)
const avatarInput  = ref(null)
const editForm     = reactive({ name: '', email: '', newPassword: '', avatarPreview: '' })
const lbl = computed(() => ['text-sm font-medium block mb-1.5', isDark.value ? 'text-slate-300' : 'text-slate-700'])

function openUserEdit() {
  editForm.name          = auth.user?.name  || ''
  editForm.email         = auth.user?.email || ''
  editForm.newPassword   = ''
  editForm.avatarPreview = userAvatar.value
  showUserEdit.value     = true
  userOpen.value         = false
}
function onAvatarChange(e) {
  const file = e.target.files?.[0]; if (!file) return
  const reader = new FileReader()
  reader.onload = ev => { editForm.avatarPreview = ev.target.result }
  reader.readAsDataURL(file); e.target.value = ''
}
async function saveUser() {
  if (auth.user) { auth.user.name = editForm.name; auth.user.email = editForm.email; localStorage.setItem('user', JSON.stringify(auth.user)) }
  userAvatar.value = editForm.avatarPreview
  localStorage.setItem('userAvatar', editForm.avatarPreview)
  showUserEdit.value = false
}

// Nav
const allMainNav = [
  { to: '/',             key: 'nav.dashboard',    icon: LayoutDashboard, exact: true },
  { to: '/patients',     key: 'nav.patients',     icon: Users, perm: 'patients:read' },
  { to: '/appointments', key: 'nav.appointments', icon: Calendar, perm: 'appointments:read' },
  { to: '/emr',          key: 'nav.emr',          icon: FileText, perm: 'emr:read' },
  { to: '/lab',          key: 'nav.lab',          icon: FlaskConical, perm: 'lab:read' },
  { to: '/finance',      key: 'nav.finance',      icon: DollarSign, perm: 'finance:read' },
  { to: '/analytics',    key: 'nav.analytics',    icon: BarChart3, perm: 'analytics:read' },
  { to: '/ai',           key: 'nav.ai',           icon: Bot, perm: 'ai:use' },
  { to: '/reports',      key: 'nav.reports',      icon: FileBarChart, perm: 'reports:read' },
  { to: '/chat',         key: 'nav.chat',         icon: MessageSquare, hidden: true },  // hozircha yashirilgan (kod saqlangan)
]
const allSystemNav = [
  { to: '/staff',        key: 'nav.staff',        icon: UserCog, perm: 'staff:read' },
  { to: '/subscription', key: 'nav.subscription', icon: CreditCard, hidden: true },  // hozircha yashirilgan (kod saqlangan)
  { to: '/security',     key: 'nav.security',     icon: Shield, perm: 'audit:read' },
  { to: '/settings',     key: 'nav.settings',     icon: Settings, perm: 'settings:read' },
]
const visible = items => items.filter(i => !i.hidden && (!i.perm || auth.can(i.perm)))
const mainNav = computed(() => visible(allMainNav))
const systemNav = computed(() => visible(allSystemNav))

const pageKeyMap = {
  '/': 'page.dashboard', '/patients': 'page.patients', '/appointments': 'page.appointments',
  '/emr': 'page.emr', '/lab': 'page.lab', '/finance': 'page.finance', '/analytics': 'page.analytics',
  '/ai': 'page.ai', '/reports': 'page.reports', '/staff': 'page.staff',
  '/subscription': 'page.subscription', '/security': 'page.security', '/settings': 'page.settings', '/chat': 'nav.chat',
}
const pageTitle   = computed(() => {
  const p = route.path
  if (p.startsWith('/patients/')) return lang.t('page.patient_profile')
  return lang.t(pageKeyMap[p] || 'page.dashboard')
})
const userInitial = computed(() => (auth.user?.name || 'A')[0].toUpperCase())
function isActive(path, exact = false) {
  if (exact) return route.path === path
  return route.path.startsWith(path)
}
async function logout() { await auth.logout(); router.push('/login') }
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity .15s, width .15s; }
.fade-enter-from, .fade-leave-to       { opacity: 0; width: 0; }
.page-enter-active { animation: pageIn  .28s ease-out; }
.page-leave-active { animation: pageOut .15s ease-in; }
.dropdown-enter-active { transition: all .15s ease-out; }
.dropdown-leave-active { transition: all .1s  ease-in; }
.dropdown-enter-from   { opacity: 0; transform: translateY(-8px) scale(.96); }
.dropdown-leave-to     { opacity: 0; }
.modal-fade-enter-active { transition: opacity .2s; }
.modal-fade-leave-active { transition: opacity .15s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }
.icon-flip-enter-active { transition: all .2s ease-out; }
.icon-flip-leave-active { transition: all .15s ease-in; }
.icon-flip-enter-from   { opacity: 0; transform: rotate(-90deg) scale(.6); }
.icon-flip-leave-to     { opacity: 0; transform: rotate(90deg)  scale(.6); }
.effect-fade-enter-active { transition: opacity .1s; }
.effect-fade-leave-active { transition: opacity .4s; }
.effect-fade-enter-from, .effect-fade-leave-to { opacity: 0; }
@keyframes pageIn  { from { opacity: 0; transform: translateY(6px); }  to { opacity: 1; transform: translateY(0); } }
@keyframes pageOut { from { opacity: 1; } to { opacity: 0; } }
</style>