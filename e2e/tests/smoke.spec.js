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
    await page.getByTestId('perform-line').click()                                 // xizmat bajarildi (sarf ombordan yoziladi)
    await expect(page.getByText('Xizmat bajarildi, sarf ombordan yozildi')).toBeVisible()
    await expect(page.locator('.badge-green', { hasText: 'Bajarildi' })).toBeVisible()
  })
})

test.describe('ombor', () => {
  test.use({ storageState: 'auth.json' })

  test('5. ombor: material, kirim (2 partiya), FEFO chiqim, ogohlantirish, hisobdan chiqarish', async ({ page }) => {
    const name = `E2E Shprits ${Date.now()}`
    const day = n => new Date(Date.now() + n * 864e5).toISOString().slice(0, 10)
    await page.goto('/warehouse')
    await page.getByTestId('wh-new-item').click()
    await page.getByTestId('item-name').fill(name)
    await page.getByTestId('item-unit').fill('dona')
    await page.getByTestId('item-min').fill('15')                               // minimal qoldiq 15: chiqimdan keyin 8 < 15
    await page.getByTestId('item-save').click()
    await expect(page.getByText('Material saqlandi')).toBeVisible()

    // Kirim: ikki partiya (kirish tartibi muddat tartibiga teskari)
    await page.getByTestId('wh-new-receipt').click()
    const modal = page.locator('.modal-overlay').last()
    await modal.getByRole('button', { name: "Qator qo'shish" }).click()
    const rows = [['E2E-LATE', day(300), '10', '500'], ['E2E-SOON', day(10), '10', '450']]
    for (const [i, [batch, exp, qty, cost]] of rows.entries()) {
      await modal.getByTestId('rcp-item').nth(i).selectOption({ label: `${name} (dona)` })
      await modal.getByTestId('rcp-batch').nth(i).fill(batch)
      await modal.locator('input[type="date"]').nth(i + 1).fill(exp)       // 0-chi: kirim sanasi
      await modal.getByTestId('rcp-qty').nth(i).fill(qty)
      await modal.getByTestId('rcp-cost').nth(i).fill(cost)
    }
    await modal.getByTestId('rcp-save').click()
    await expect(page.getByText('Kirim saqlandi')).toBeVisible()
    await expect(page.getByTestId('wh-stock').getByRole('row', { name: new RegExp(name) })).toContainText('20')

    // Muddati 30 kunda tugaydigan partiya ogohlantiradi
    await expect(page.getByTestId('wh-alerts')).toContainText('kunda muddati tugaydi')

    // FEFO chiqim: 12 ta = avval E2E-SOON (10), keyin E2E-LATE (2)
    await page.getByTestId('wh-new-issue').click()
    const issue = page.locator('.modal-overlay').last()
    await issue.getByTestId('iss-item').selectOption({ label: `${name} (dona)` })
    await issue.getByTestId('iss-qty').fill('12')
    await issue.getByTestId('iss-reason').fill('E2E 3-kabinet')
    await issue.getByTestId('iss-save').click()
    const result = issue.getByTestId('iss-result')
    await expect(result).toContainText('partiya E2E-SOON')
    await expect(result).toContainText('partiya E2E-LATE')
    await issue.getByRole('button', { name: 'Yopish' }).click()

    // Qolgan 8 ta LATE hisobdan chiqariladi
    await page.getByTestId('wh-tab-batches').click()
    const batchRow = page.getByTestId('wh-batches').getByRole('row', { name: /E2E-LATE/ })
    await expect(batchRow).toContainText('8')
    await batchRow.getByTestId('wh-writeoff').click()
    await page.getByTestId('wo-reason').fill('E2E singan')
    await page.getByTestId('wo-save').click()
    await expect(page.getByText('Hisobdan chiqarildi')).toBeVisible()
    await page.getByTestId('wh-tab-movements').click()
    await expect(page.getByTestId('wh-movements')).toContainText('Hisobdan chiqarish')
    await expect(page.getByTestId('wh-movements')).toContainText('Chiqim')

    // Minimaldan kam: ombor mas'uliga bildirishnoma (qo'ng'iroqcha)
    await page.reload()
    await page.getByTestId('notif-bell').click()
    await expect(page.getByTestId('notif-list')).toContainText(`Minimal qoldiqdan kam: ${name}`)
  })
})

test.describe('filiallar', () => {
  test.use({ storageState: 'auth.json' })

  test('6. filial: Sozlamalarda yaratish, faol filialni almashtirish, ombor filial bo\'yicha', async ({ page }) => {
    const name = `E2E Filial ${Date.now()}`
    await page.goto('/settings')
    await page.getByRole('button', { name: 'Filiallar' }).click()
    await page.getByTestId('branch-new').click()
    await page.getByTestId('branch-name').fill(name)
    await page.getByTestId('branch-save').click()
    await expect(page.getByText('Filial saqlandi')).toBeVisible()
    await expect(page.getByTestId('branch-table').getByRole('row', { name: new RegExp(name) })).toBeVisible()

    // Faol filialni almashtirish (sahifa qayta yuklanadi), keyin yangi filial "Faol" deb belgilanadi
    await page.reload()
    const select = page.getByTestId('branch-select')
    await expect(select).toBeVisible()
    await Promise.all([page.waitForEvent('load'), select.selectOption({ label: name })])
    await page.goto('/settings')
    await page.getByRole('button', { name: 'Filiallar' }).click()
    await expect(page.getByTestId('branch-table').getByRole('row', { name: new RegExp(name) })).toContainText('Faol')

    // Yangi filialning ombori bo'sh: katalog umumiy, qoldiq 0
    await page.goto('/warehouse')
    await expect(page.getByTestId('wh-stock')).toBeVisible()
    await expect(page.getByTestId('wh-stock').locator('tbody tr').first()).toContainText('0')
  })
})

test.describe('tannarx', () => {
  test.use({ storageState: 'auth.json' })

  test('7. narxnoma: sarf normasi va tannarx ombor narxidan avtomatik hisoblanadi', async ({ page, request }) => {
    const stamp = Date.now()
    const login = await request.post('/api/auth/login', { data: ADMIN })
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
    const svc = await (await request.post('/api/services', { headers, data: { name: `E2E Tannarx ${stamp}`, price: 112000, mxik: '09302001001000000', package_code: '1500364', vat_percent: 12 } })).json()
    const item = await (await request.post('/api/warehouse/items', { headers, data: { name: `E2E Material ${stamp}`, unit: 'dona' } })).json()
    const exp = new Date(Date.now() + 200 * 864e5).toISOString().slice(0, 10)
    const receive = async (batch, cost) => expect((await request.post('/api/warehouse/receipts', { headers, data: { lines: [
      { item_id: item.id, batch_no: batch, qty: 100, unit_cost: cost, expires_on: exp }] } })).ok()).toBeTruthy()
    await receive('T-1', 450)

    await page.goto('/settings')
    await page.getByRole('button', { name: 'Narxnoma' }).click()
    await page.getByPlaceholder('Xizmat qidirish...').fill(svc.name)
    const row = page.getByRole('row', { name: new RegExp(svc.name) })
    await row.getByTestId('svc-norms').click()
    await page.getByTestId('norm-add').click()
    await page.getByTestId('norm-item').selectOption({ label: `${item.name} (dona)` })
    await page.getByTestId('norm-qty').fill('2')
    await page.getByTestId('norm-save').click()
    await expect(page.getByText('Sarf normasi saqlandi')).toBeVisible()
    await expect(page.getByTestId('norm-cost')).toContainText('Tannarx 900')                 // 2 x 450
    await page.getByRole('button', { name: 'Yopish' }).click()
    await expect(row.getByTestId('svc-cost')).toContainText('900')

    await receive('T-2', 550)                                                                  // yangi kirim narxi: o'rtacha (450+550)/2 = 500
    await page.reload()
    await page.getByRole('button', { name: 'Narxnoma' }).click()
    await page.getByPlaceholder('Xizmat qidirish...').fill(svc.name)
    await expect(page.getByRole('row', { name: new RegExp(svc.name) }).getByTestId('svc-cost')).toContainText(/1[,\s]?000/)   // 2 x 500
  })
})

test.describe('dashboard', () => {
  test.use({ storageState: 'auth.json' })

  test('8. dashboard: ombor ogohlantirishi va "hamma filial birga" hisobi', async ({ page, request }) => {
    const login = await request.post('/api/auth/login', { data: ADMIN })
    const headers = { Authorization: `Bearer ${(await login.json()).access_token}` }
    const item = await (await request.post('/api/warehouse/items', { headers, data: { name: `E2E Dash ${Date.now()}`, unit: 'dona', min_qty: 5 } })).json()
    expect(item.id).toBeTruthy()                                      // qoldiq 0 < minimal 5: ogohlantirish chiqadi
    await page.goto('/')
    const alert = page.getByTestId('dash-stock-alert')
    await expect(alert).toBeVisible()
    await expect(alert).toContainText('minimaldan kam')
    await alert.click()
    await expect(page).toHaveURL(/\/warehouse/)

    await page.goto('/')
    const toggle = page.getByTestId('dash-all-branches')
    await expect(toggle).toBeVisible()
    const responded = page.waitForResponse(r => r.url().includes('/analytics/dashboard') && r.url().includes('all_branches=true'))
    await toggle.check()
    expect((await responded).status()).toBe(200)
  })
})

test('8. onlayn yozilish: bir nechta filialda avval filial tanlanadi', async ({ page }) => {
  await page.goto('/p/book')
  await expect(page.getByTestId('book-branches')).toBeVisible()
  await page.getByTestId('book-branch').first().click()
  await expect(page.getByText('Xizmatni tanlang')).toBeVisible()
})

test('9. portal: OTP, ikki til, qabullar, hisoblar, tahlillar (PDF), qabulni bekor qilish', async ({ page, request }) => {
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

  // Yangi qabulga yozilish (filial tanlab): bo'sh vaqtdan birini band qilish
  await page.getByTestId('tab-book').click()
  await expect(page.getByTestId('portal-book')).toBeVisible()
  await page.getByTestId('portal-book-branch').selectOption({ index: 0 })        // asosiy filial (bir nechta filial bor)
  await page.getByTestId('portal-book-doctor').selectOption({ label: DOCTOR })
  await page.getByTestId('portal-book-date').fill(nextWorkday())
  await page.getByTestId('portal-slot').first().click()
  await page.getByTestId('portal-book-save').click()
  await expect(page.getByTestId('portal-book-done')).toContainText(DOCTOR)
  await page.getByTestId('tab-appointments').click()
  await expect(appts.filter({ hasText: 'Rejalashtirilgan' })).toHaveCount(1)
  await expect(page.getByTestId('portal-branch').first()).toBeVisible()

  // Chiqish: seans tugaydi, kirish formasi qaytadi
  await page.getByTestId('portal-logout').click()
  await expect(page.getByTestId('portal-phone')).toBeVisible()
})
