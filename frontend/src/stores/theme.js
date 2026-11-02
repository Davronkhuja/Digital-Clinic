import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// ── Theme definitions ──────────────────────────────────────────────────────
export const THEMES = [
  {
    id: 'cyan',
    name: 'Cyan Ocean',
    desc: 'Klassik ko\'k-moviy',
    emoji: '🌊',
    primary: 'from-cyan-500 to-blue-600',
    accent: '#06b6d4',
    accentSecond: '#2563eb',
    vars: {
      '--c-primary': '6 182 212',
      '--c-secondary': '37 99 235',
      '--c-sidebar-dark': '15 23 42',
      '--c-sidebar-light': '255 255 255',
    },
    effect: 'wave',
    preview: 'bg-gradient-to-br from-cyan-500 to-blue-600',
  },
  {
    id: 'violet',
    name: 'Violet Dusk',
    desc: 'Binafsha tungi',
    emoji: '🌌',
    primary: 'from-violet-500 to-purple-700',
    accent: '#8b5cf6',
    accentSecond: '#7c3aed',
    vars: {
      '--c-primary': '139 92 246',
      '--c-secondary': '124 58 237',
      '--c-sidebar-dark': '20 10 40',
      '--c-sidebar-light': '250 248 255',
    },
    effect: 'stars',
    preview: 'bg-gradient-to-br from-violet-500 to-purple-700',
  },
  {
    id: 'emerald',
    name: 'Emerald Forest',
    desc: 'Yashil tabiat',
    emoji: '🌿',
    primary: 'from-emerald-500 to-teal-600',
    accent: '#10b981',
    accentSecond: '#0d9488',
    vars: {
      '--c-primary': '16 185 129',
      '--c-secondary': '13 148 136',
      '--c-sidebar-dark': '2 20 14',
      '--c-sidebar-light': '240 253 244',
    },
    effect: 'leaves',
    preview: 'bg-gradient-to-br from-emerald-500 to-teal-600',
  },
  {
    id: 'rose',
    name: 'Rose Bloom',
    desc: 'Pushti gul',
    emoji: '🌸',
    primary: 'from-rose-500 to-pink-600',
    accent: '#f43f5e',
    accentSecond: '#ec4899',
    vars: {
      '--c-primary': '244 63 94',
      '--c-secondary': '236 72 153',
      '--c-sidebar-dark': '30 5 15',
      '--c-sidebar-light': '255 241 242',
    },
    effect: 'petals',
    preview: 'bg-gradient-to-br from-rose-500 to-pink-600',
  },
  {
    id: 'amber',
    name: 'Amber Sunrise',
    desc: 'Oltin tong',
    emoji: '🌅',
    primary: 'from-amber-500 to-orange-600',
    accent: '#f59e0b',
    accentSecond: '#ea580c',
    vars: {
      '--c-primary': '245 158 11',
      '--c-secondary': '234 88 12',
      '--c-sidebar-dark': '28 14 2',
      '--c-sidebar-light': '255 251 235',
    },
    effect: 'rays',
    preview: 'bg-gradient-to-br from-amber-500 to-orange-600',
  },
  {
    id: 'slate',
    name: 'Midnight Steel',
    desc: "Metall po'lat",
    emoji: '⚙️',
    primary: 'from-slate-600 to-slate-800',
    accent: '#64748b',
    accentSecond: '#334155',
    vars: {
      '--c-primary': '100 116 139',
      '--c-secondary': '51 65 85',
      '--c-sidebar-dark': '2 6 23',
      '--c-sidebar-light': '248 250 252',
    },
    effect: 'grid',
    preview: 'bg-gradient-to-br from-slate-500 to-slate-700',
  },
]

export const useThemeStore = defineStore('theme', () => {
  const isDark     = ref(localStorage.getItem('theme') === 'dark')
  const themeId    = ref(localStorage.getItem('themeId') || 'cyan')
  const currentTheme = ref(THEMES.find(t => t.id === themeId.value) || THEMES[0])

  function applyTheme() {
    if (isDark.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    // Apply CSS vars
    const t = currentTheme.value
    if (t?.vars) {
      const root = document.documentElement
      Object.entries(t.vars).forEach(([k, v]) => root.style.setProperty(k, v))
    }
    // Primary color classes on <html> for global usage
    document.documentElement.setAttribute('data-theme', currentTheme.value?.id || 'cyan')
  }

  function toggle() {
    isDark.value = !isDark.value
    localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
    applyTheme()
  }

  function setTheme(id) {
    const t = THEMES.find(th => th.id === id)
    if (!t) return
    themeId.value = id
    currentTheme.value = t
    localStorage.setItem('themeId', id)
    applyTheme()
  }

  applyTheme()

  return { isDark, themeId, currentTheme, toggle, setTheme, themes: THEMES }
})