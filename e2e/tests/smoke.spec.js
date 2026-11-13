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

test('5. portal: telefon + OTP bilan kirish', async ({ page }) => {
  await page.goto('/portal')
  await page.getByTestId('portal-phone').fill(PATIENT.phone)
  await page.getByTestId('portal-send').click()
  await page.getByTestId('portal-code').fill(await waitForOtp(PATIENT.phone))
  await page.getByTestId('portal-verify').click()
  await expect(page.getByTestId('portal-patient')).toHaveText(PATIENT.name)
  await expect(page.getByTestId('portal-appointments').locator('article')).not.toHaveCount(0)
  await page.getByTestId('tab-invoices').click()
  await expect(page.getByTestId('portal-invoices').locator('article')).not.toHaveCount(0)
  await page.getByTestId('tab-lab').click()
  await expect(page.getByTestId('portal-lab')).toBeVisible()
})
