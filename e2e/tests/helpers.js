import { execSync } from 'node:child_process'

export const ADMIN = { email: process.env.E2E_EMAIL || 'admin@clinic.uz', password: process.env.E2E_PASSWORD || 'password123' }

// Mock SMS matni backend jurnaliga yoziladi (`app.sms.mock`): OTP shu yerdan o'qiladi.
const LOG_CMD = process.env.E2E_LOG_CMD || 'docker compose logs backend --no-log-prefix --tail 300'

export function lastOtp(phone) {
  const digits = phone.replace(/\D/g, '')
  const out = execSync(`${LOG_CMD} 2>&1`, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
  const hits = [...out.matchAll(new RegExp(`MOCK SMS to=\\+?${digits} text=.*?(\\d{6})`, 'g'))]
  return hits.length ? hits[hits.length - 1][1] : null
}

export async function waitForOtp(phone, timeoutMs = 15_000) {
  const end = Date.now() + timeoutMs
  while (Date.now() < end) {
    const code = lastOtp(phone)
    if (code) return code
    await new Promise(r => setTimeout(r, 500))
  }
  throw new Error(`OTP kodi jurnalda topilmadi: ${phone}`)
}

// Keyingi dushanba-payshanba kuni (shifokor jadvali: Du-Ju 09-17), kamida 3 kun keyin, YYYY-MM-DD
export function nextWorkday() {
  const d = new Date(Date.now() + 3 * 864e5)
  while (d.getDay() === 0 || d.getDay() === 5 || d.getDay() === 6) d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

// Har yurishda yangi telefon va ism: bir bazada takror yurganda to'qnashmasin
const rnd = String(Math.floor(Math.random() * 9_000_000) + 1_000_000)
export const PATIENT = {
  name: `Sinov Bemor ${rnd}`,
  phone: `+998 90 ${rnd.slice(0, 3)}-${rnd.slice(3, 5)}-${rnd.slice(5, 7)}`,
}
