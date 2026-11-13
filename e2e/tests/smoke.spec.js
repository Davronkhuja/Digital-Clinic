import { test, expect } from '@playwright/test'
import { ADMIN, PATIENT, nextWorkday, waitForOtp } from './helpers.js'

const DOCTOR = 'Dr. Behruz Rustamov'
test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ request }) => {
  // Demo bazada narxnoma bo'sh: kassa uchun sotiladigan xizmat API orqali (MXIK, package_code, QQS bilan)
  const login = await request.post('/api/auth/login', { data: ADMIN })
  expect(login.ok()).toBeTruthy()
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
  const list = await (await request.get('/api/services', { headers })).json()
  if (!list.some(s => s.sellable)) {
    const made = await request.post('/api/services', { headers, data: {
      name: 'E2E konsultatsiya', price: 100000, mxik: '09302001001000000', package_code: '1500364', vat_percent: 12 } })
    expect(made.ok()).toBeTruthy()
  }
})

test('1. login: xodim tizimga kiradi', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder('admin@clinic.uz').fill(ADMIN.email)
  await page.getByPlaceholder('••••••••').fill(ADMIN.password)
  await page.locator('button[type="submit"]').click()
  await expect(page).not.toHaveURL(/\/login/)
  await expect(page.getByText('Kassa').first()).toBeVisible()
  await page.context().storageState({ path: 'auth.json' })
})

test.describe('kirgan xodim', () => {
  test.use({ storageState: 'auth.json' })

  test('2. bemor qo\'shish', async ({ page }) => {
    await page.goto('/patients')
    await page.getByRole('button', { name: 'Yangi bemor' }).click()
    await page.getByPlaceholder('Aziza Karimova').fill(PATIENT.name)
    await page.getByPlaceholder('+998 90 123-45-67').fill(PATIENT.phone)
    await page.getByRole('button', { name: 'Saqlash' }).click()
    await expect(page.getByText("Bemor qo'shildi")).toBeVisible()
    await page.getByPlaceholder(/Ism, telefon/).fill(PATIENT.name)
    await expect(page.getByText(PATIENT.name).first()).toBeVisible()
  })

  test('3. qabul yozish', async ({ page }) => {
    await page.goto('/appointments')
    await page.getByRole('button', { name: "Uchrashuv qo'shish" }).first().click()
    const form = page.locator('.modal-overlay form')
    await form.getByPlaceholder('Aziza Karimova').fill(PATIENT.name)
    await form.locator('select').first().selectOption(DOCTOR)
    await form.locator('input[type="date"]').fill(nextWorkday())
    const slot = form.locator('button.font-mono').first()      // bo'sh vaqt tugmasi
    await expect(slot).toBeVisible()
    await slot.click()
    await form.getByRole('button', { name: 'Saqlash' }).click()
    await expect(page.getByText('Uchrashuv rejalashtirildi')).toBeVisible()
  })

  test('4. kassa: hisob-faktura, naqd to\'lov va chek', async ({ page }) => {
    await page.goto('/cashier')
    const open = page.getByRole('button', { name: 'Smenani ochish' })
    await expect(open.or(page.getByText('Smena ochiq'))).toBeVisible()      // smena holati yuklangach
    if (await open.isVisible()) {
      await open.click()
      await page.locator('.modal-overlay').getByRole('button', { name: 'Ochish', exact: true }).click()
    }
    await expect(page.getByText('Smena ochiq')).toBeVisible()
    await page.getByRole('button', { name: 'Yangi hisob-faktura' }).click()
    const modal = page.locator('.modal-overlay').last()
    await modal.getByPlaceholder('Aziza Karimova').fill(PATIENT.name)
    await modal.locator('select').nth(1).selectOption({ index: 1 })    // birinchi xizmat
    await modal.getByRole('button', { name: 'Yaratish' }).click()
    await expect(page.getByText('Hisob-faktura chiqarildi')).toBeVisible()
    await page.getByPlaceholder('Raqam yoki bemor...').fill(PATIENT.name)
    await page.getByRole('button', { name: 'Ochish', exact: true }).first().click()
    await page.getByRole('button', { name: "To'lov qabul qilish" }).click()    // usul: Cash
    await expect(page.getByText(/chek \S+/).first()).toBeVisible()               // fiskal chek ID (mock)
  })
})

test('5. portal: OTP, ikki til, qabullar, hisoblar, tahlillar (PDF), qabulni bekor qilish', async ({ page, request }) => {
  // Tahlil: tasdiqlangan natija API orqali tayyorlanadi (portal faqat shifokor tasdiqlaganini ko'rsatadi)
  const login = await request.post('/api/auth/login', { data: ADMIN })
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
  const patients = await (await request.get('/api/patients', { headers, params: { search: PATIENT.name } })).json()
  const patient = patients.find(p => p.name === PATIENT.name)
  const test = (await (await request.get('/api/lab/tests', { headers })).json()).find(t => t.is_active)
  const order = await (await request.post('/api/lab/orders', { headers, data: { patient_id: patient.id, doctor: DOCTOR, test_ids: [test.id] } })).json()
  expect((await request.put(`/api/lab/orders/${order.id}/results`, { headers, data: { results: [{ item_id: order.items[0].id, value: 5 }] } })).ok()).toBeTruthy()
  expect((await request.post(`/api/lab/orders/${order.id}/approve`, { headers })).ok()).toBeTruthy()

  // Kirish
  await page.goto('/portal')
  await page.getByTestId('portal-phone').fill(PATIENT.phone)
  await page.getByTestId('portal-send').click()
  await page.getByTestId('portal-code').fill(await waitForOtp(PATIENT.phone))
  await page.getByTestId('portal-verify').click()
  await expect(page.getByTestId('portal-patient')).toHaveText(PATIENT.name)

  // Qabullar (o'zbekcha), keyin rus tiliga o'tish
  const appts = page.getByTestId('portal-appointments').locator('article')
  await expect(appts).toHaveCount(1)
  await expect(page.getByTestId('tab-appointments')).toHaveText('Qabullar')
  await expect(appts.first()).toContainText('Rejalashtirilgan')
  await page.getByTestId('lang-ru').click()
  await expect(page.getByRole('heading', { name: 'Портал пациента' })).toBeVisible()
  await expect(page.getByTestId('tab-appointments')).toHaveText('Приёмы')
  await expect(appts.first()).toContainText('Запланирован')

  // Hisoblar (rus tilida): to'liq to'langan
  await page.getByTestId('tab-invoices').click()
  const invoices = page.getByTestId('portal-invoices').locator('article')
  await expect(invoices).toHaveCount(1)
  await expect(invoices.first()).toContainText('Итого')
  await expect(invoices.first()).toContainText('Оплачено')
  await expect(invoices.first()).not.toContainText('Долг')

  // Tahlillar: tasdiqlangan natija va PDF
  await page.getByTestId('tab-lab').click()
  const labs = page.getByTestId('portal-lab').locator('article')
  await expect(labs).toHaveCount(1)
  await expect(labs.first()).toContainText(test.name)
  const [pdf] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/pdf')),
    page.getByTestId('portal-lab-pdf').click(),
  ])
  expect(pdf.status()).toBe(200)
  expect(pdf.headers()['content-type']).toContain('application/pdf')

  // O'zbek tiliga qaytish va qabulni bekor qilish (tasdiq bilan)
  await page.getByTestId('lang-uz').click()
  await page.getByTestId('tab-appointments').click()
  await page.getByTestId('portal-cancel').click()
  await expect(page.getByText('Qabulni bekor qilishni tasdiqlaysizmi?')).toBeVisible()
  await page.getByTestId('portal-cancel-yes').click()
  await expect(appts.first()).toContainText('Bekor qilingan')
  await expect(page.getByTestId('portal-cancel')).toHaveCount(0)

  // Chiqish: seans tugaydi, kirish formasi qaytadi
  await page.getByTestId('portal-logout').click()
  await expect(page.getByTestId('portal-phone')).toBeVisible()
})
