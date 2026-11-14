# Digital Clinic: Claude uchun loyiha yo'riqnomasi

Yangi sessiya shu fayldan boshlasin: u loyiha, qoidalar, qabul qilingan qarorlar va reja haqidagi yagona manba.

## Loyiha

Xususiy klinikalar uchun boshqaruv tizimi (bemorlar, uchrashuvlar, EMR, moliya, tahlil, rollar, audit).

- **Mijoz: faqat xususiy klinikalar. DMED va boshqa davlat tizimlariga integratsiya QILINMAYDI.**
  (Ko'rik kartasi DMED maydonlari tartibida bo'ladi, "DMED ga ko'chirildi" belgisi qo'lda qo'yiladi: API yo'q.)
- `AI_ENABLED=false` standart. AI demo rejimida: tashqi so'rov yo'q, statik javoblar, "Demo rejim" belgisi.
  LLM kodi (OpenAI-mos: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`) saqlangan, faqat flag bilan o'chirilgan. Yoqish faqat 6-bosqichda.
- Stack: FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL 16 (`backend/`), Vue 3 + Vite + Pinia + Tailwind (`frontend/`), Docker Compose.
- Portlar: frontend http://localhost:5180, backend http://localhost:8010 (Swagger `/docs`). PostgreSQL host portiga ochilmagan.
  **8080 portiga TEGMA: u yerda boshqa loyiha ishlaydi.**
- Repo: github.com/Davronkhuja/Digital-Clinic (shaxsiy, branch `main`). `origin` HTTPS (`https://github.com/Davronkhuja/Digital-Clinic.git`),
  autentifikatsiya `gh auth setup-git` orqali (SSH `Permission denied (publickey)` bilan o'zgaruvchan edi, shuning uchun HTTPS'ga o'tilgan).
- Til: foydalanuvchi bilan va UI/commit/CHANGELOG matnlarida o'zbekcha.

## Ish qoidalari

1. **Bitta band = bitta commit = bitta versiya (SemVer). Bir nechta bandni bitta commitga birlashtirma** (mashina sekin yoki testlar uzoq bo'lsa ham:
   har band alohida testlanadi, commit qilinadi, tag qo'yiladi). v1.7.10-v1.8.7 bitta commit bo'lib chiqqan va push qilingan: uni qayta yozma, faqat takrorlama.
   Xato tuzatish PATCH, yangi imkoniyat yoki ichki qayta qurish MINOR,
   API'ni buzadigan o'zgarish MAJOR. Joriy bosqichlar uchun raqamlash: 1-bosqich v1.5.x, 2-bosqich v1.6.x, 3: v1.7.x, 4: v1.8.x, 5: v1.9.x, 6: v2.0.0
   (hujjatdagi v1.3-v2.0 raqamlariga qaralmaydi). Joriy versiya: `VERSION` faylida.
2. Versiya uch joyda bir vaqtda: `VERSION`, `frontend/package.json`, `backend/app/__init__.py` (`__version__`):
   `scripts/bump-version.sh X.Y.Z`. FastAPI `version=` shu o'zgaruvchidan o'qiydi.
3. `CHANGELOG.md` (Keep a Changelog) ga yozuv: versiya, sana, nima o'zgardi.
4. Commit: Conventional Commits (`feat(...)`, `fix(...)`, `security:`, `refactor(...)`, `test:`, `ci:`, `docs:`, `chore:`),
   matnda qaysi band hal qilingani. Commit oxirida attribution qatori (tizim eslatmasidagi `Co-Authored-By`).
5. Commitdan keyin `git tag -a vX.Y.Z -m "..."`. **Har versiya tagidan keyin `git push origin main --follow-tags` bilan push qil.
   Boshqa ko'rinishda (force, `git -C`, boshqa branch) push qilma. Rad etilsa, chetlab o'tma: to'xta va xabar ber.**
6. **Sirlar faqat `.env` da** (parol, API kalit, JWT secret); repoda faqat `.env.example`. Har commitdan oldin:
   `git diff --cached | grep -iE "gsk_|secret|password="` (JWT_SECRET/PASSWORD nomlari va test parollari kutilgan hit).
7. Har vazifadan keyin: `docker compose up -d --build`, konteynerlar healthy/running; testlar o'tsin (quyida). O'tmasa commit qilma.
8. Noaniqlik yoki qaytarib bo'lmaydigan qaror (sxema, ma'lumotni o'chirish) bo'lsa: to'xta va so'ra. Mock'dan real integratsiyaga o'tishda
   (to'lov, SMS, fiskal chek) real API hujjatlari bo'lmasa, mock'da to'xta va so'ra.
9. **Docker: faqat build keshiga tegish mumkin (`docker builder prune`). Volume, imaj va boshqa loyiha konteynerlariga TEGMA**
   (disk to'lsa, foydalanuvchi o'zi tozalaydi).
10. Har bosqich oxirida uning "Shart"ini test yoki skript bilan isbotla va qisqa hisobot ber (versiya, nima qilindi, nima qoldi).
11. Mexanik frontend ishlarini subagentga berish mumkin, lekin natijani brauzerda tekshir (agentlar brauzerda sinamaydi).
    Backend o'zgarishdan keyin `docker compose build backend` shart: `docker compose run` eski imajni ishlatadi.
12. **Docker disk:** Docker VM diski tez to'ladi (Postgres `No space left on device` bilan crash bo'ladi, `docker compose ... --build test` har safar yangi imaj qatlami yaratadi).
    `--build` ni faqat kod o'zgarganda ishlat. Disk to'lsa: faqat `docker builder prune -f`, qolganini foydalanuvchi tozalaydi.
13. `.github/workflows/*` ni push qilish uchun `gh` tokenida `workflow` scope kerak (`gh auth refresh -h github.com -s workflow`, brauzer tasdig'i; foydalanuvchi bajaradi).

## Buyruqlar

```bash
docker compose up -d --build                           # hammasi
docker compose --profile test run --rm --build test    # pytest (alohida <POSTGRES_DB>_test bazasi)
ruff check backend                                     # backend lint
cd frontend && npm run lint && npm run build           # frontend lint va build
cd e2e && npm ci && npx playwright install chromium && npx playwright test   # e2e smoke (stek ishlab turishi kerak; CI: alohida `e2e` job, `clinic_e2e` bazasi)
docker compose exec backend alembic revision --autogenerate -m "..." --rev-id NNNN   # migratsiya; faylni docker cp bilan chiqarib ol
```

CI: `.github/workflows/ci.yml` (lint -> pytest -> frontend build -> docker build); faqat `main` push va `pull_request` (tag push'da ishlamaydi).
`gh run list` / `gh run watch <id> --exit-status` bilan kuzat; qizil bo'lsa tuzat va qayta push qil. Ruff versiyasi CI va `backend/requirements-dev.txt` da bir xil bo'lsin.

Lokal `.env`da `SEED_DEMO=true` (demo hisoblar, parol `password123`: `admin@clinic.uz`, `rustamov@clinic.uz` doctor,
`yusupova@clinic.uz` nurse, `mirzayev@clinic.uz` receptionist, `akbarova@clinic.uz` cashier). `.env` gitda yo'q.
Brauzer sinovi uchun: login API'dan token olib `localStorage` (`token`, `refresh_token`, `user`) ga yoz, sahifani qayta yukla.

## Backend tuzilmasi

`backend/app/`: `main.py`, `core/` (config = pydantic-settings, security = JWT/bcrypt, deps = `get_current_user`, `require("perm")`,
permissions = ruxsatlar katalogi va standart rollar), `db/` (base, session), `models/`, `schemas/`, `routers/<bo'lim>.py`,
`services/` (queries = join bilan ro'yxatlar, serializers, audit, auth, analytics, periods, llm, lookup, scheduling/availability/booking = qabul qoidalari, icd10, inn, lab, emr_card, pdf), `seed.py`. Migratsiyalar: `backend/alembic/versions/`.

## Qabul qilingan qarorlar (o'zgartirma, so'ramasdan)

- **PK:** Postgres native `UUID`, server tomonida (`gen_random_uuid()`). API'da ID lar satr.
- **Enum va statuslar:** SQLAlchemy `Enum(native_enum=False)` + CHECK (migratsiya oson). Qiymatlar API bilan bir xil (`Active`, `Doctor`, ...).
- **Pul:** `numeric(14,2)` (`Decimal`); float DB'da va hisobda ishlatilmaydi. JSON'ga son sifatida chiqadi (`Money` turi).
- **O'chirmaslik:** EMR (`encounters`), retsept (`prescriptions`) va to'lov (`transactions`) yozuvlari hech qachon o'chirilmaydi, faqat `deleted_at`.
  Yozuvi bor bemor/xodim o'chirilmaydi (409), faolsizlantiriladi.
- **Hamma jadvalda** `created_at/updated_at` (timestamptz), `created_by`, asosiy jadvallarda `branch_id` (standart filial seed qilinadi).
  **`created_by` da FK YO'Q** (users -> staff -> branches -> users aylanma bog'liqligi uchun).
- **Rollar:** `users.role_id -> roles` (admin, doctor, nurse, receptionist, cashier); `staff.role` esa lavozim (ko'rsatish uchun).
  Ruxsatlar bazada (`roles`, `permissions`, `role_permissions`), Sozlamalar sahifasidan tahrirlanadi; admin roli o'zgarmaydi.
  Backend `require("perm")` bilan tekshiradi, frontend menyu va marshrutni `auth.can()` bilan.
- **Bemor:** `birth_date` saqlanadi (`age` hisoblanadi); `pinfl` 14 raqam, unikal, null bo'lishi mumkin.
- **API javobida** `doctor` va `patient_name` join orqali qaytadi (DB'da matn saqlanmaydi), frontend buzilmasin.
- **Autentifikatsiya:** access JWT 30 daqiqa, refresh 7 kun bazada (`jti`, `revoked_at`), har refresh'da aylantiriladi, bekor qilingan token
  qayta ishlatilsa butun oila bekor qilinadi. Logout, parol o'zgarishi, sessiyani bekor qilish refresh'ni bekor qiladi (amaldagi access <=30 daqiqa ishlaydi).
- **Register yo'q:** xodim va loginni faqat admin yaratadi (`POST /users`). Parolni tiklash yo'q (UI: "administratorga murojaat qiling").
- **SEED_DEMO** standart `false`. `false` va bazada foydalanuvchi bo'lmasa `ADMIN_EMAIL`/`ADMIN_PASSWORD` (>=10 belgi) majburiy, aks holda backend ishga tushmaydi.
  Demo faqat bo'sh bazaga. Seed idempotent.
- **Audit:** bemor, EMR, to'lov yozuvlarini o'qish/yozish, hisobot yuklab olish, kirish hodisalari, rol/foydalanuvchi o'zgarishlari `audit_log` ga
  (asosiy amal bilan bitta tranzaksiyada). IP: `X-Forwarded-For` faqat `TRUSTED_PROXIES` dan, o'ngdan birinchi ishonchsiz manzil.
- **Analitika:** hamma raqam bazadan; `period` aylanma oyna: week=7, month=30, year=365 kun, all=chegarasiz. Frontendda qattiq yozilgan raqam bo'lmasin.
- **Vaqt:** qabul `starts_at/ends_at` timestamptz (UTC), klinika vaqti Asia/Tashkent faqat ko'rsatishda; haftalik shablon devor soati (`time`).
  ORM da `Appointment.date/.time` hybrid (klinika vaqti). Ish oynasi: ExtraWork > ta'til/kasallik/dam olish > shablon; shablonsiz shifokor cheklovsiz.
- **Band vaqt:** `no_doctor_overlap` va `no_room_overlap` exclusion cheklovlar (`btree_gist`, DB foydalanuvchisi superuser), 409. Faqat `Scheduled`/`Completed` band.
- **Katalog yozuvlari o'chirilmaydi:** qabul turi, kabinet, tahlil faolsizlantiriladi; lab natijasiga nom/birlik/me'yor nusxalanadi.
  Retsept (`deleted_at`) va lab buyurtma (status `Cancelled`) o'chirilmaydi. Mos me'yor bo'lmasa (bola, yosh noma'lum) lab belgisi null.
- **Ruxsatlar:** `patients:merge`, `lab:read/write`, `appointments:override`, `services:read/write`, `finance:discount/refund/shifts`,
  `commissions:read/manage` (data migratsiya mavjud rollarga beradi; yangi ruxsat qo'shsangiz migratsiyada ham bering).
  Rollar: admin, doctor, nurse, receptionist, **senior_receptionist** (majburan yozish), cashier.
- **Pul:** bazada `numeric(14,2)` (Decimal); so'm <-> tiyin va yaxlitlash FAQAT `services/money.py` (`q2`, `to_tiyin`, `from_tiyin`); Payme/Click shundan foydalanadi
  (testda tekshiriladi). Narx QQS bilan, QQS ichidan ajratiladi (`net*p/(100+p)`). Hisob-faktura qatoriga xizmat nomi, narx, MXIK, QQS nusxalanadi.
- **To'lov:** Cash/Card kassada (ochiq smena shart, chek berilmasa yozilmaydi 502); Payme/Click `Pending` (summa band) -> provayder chaqiruvi bilan `Paid`
  (chek xatosi provayderga qaytmaydi: `receipt_status=Failed`, `POST /payments/{id}/receipt` bilan qayta). To'lov va qaytarish `transactions` ga
  (`payment_id`/`refund_id`) avtomatik yoziladi. Qaytarish faqat `finance:refund` + ochiq smena; Payme -2 avtomatik qaytaradi; Click qaytarishi yozilmagan.
- **Smena:** bir kassirda bitta ochiq smena; yopilganda Z-raqam va qotgan snapshot; onlayn to'lovlar smenaga bog'lanmaydi.
- **Kalitlar** (`PAYME_*`, `CLICK_*`, `FISCAL_BACKEND`) faqat `.env`; bo'sh kalit: endpoint hamma so'rovni rad etadi; `*_TEST_MODE=true` standart (sandbox).
- **Lab tasdiqi:** tasdiqlangan (`lab:approve`) natija tahrirlanmaydi (PUT 409, tasdiqni qaytarish yo'q); o'zgartirish faqat `POST /lab/orders/{id}/corrections`
  (`lab_corrections`: sabab majburiy, kim, qachon, eski/yangi qiymat; o'chirilmaydi; audit). Bemor portali va bot faqat tasdiqlanganini ko'rsatadi.
- **Bemor portali:** `/portal` (telefon + OTP, uz/ru, mobil); seans `sessionStorage`da, xodim tokenidan alohida axios. Mock SMS matni (OTP) oddiy jurnalga YOZILMAYDI: faqat dev/test outbox faylga (`MOCK_SMS_OUTBOX`, 0600), e2e OTP'ni shundan oladi.
  `APP_ENV=production` (yoki `ENV`) da `SMS_BACKEND=mock` va `MOCK_SMS_OUTBOX` bilan backend ishga tushmaydi. OTP: 5 daqiqa, 5 xato urinishdan keyin telefon 15 daqiqaga bloklanadi (429),
  telefon (15 daqiqada 3) va IP (so'rov soatiga 10, tasdiqlash soatiga 30) bo'yicha cheklov; yuborilgach xabar matnidagi kod bazadan ham o'chiriladi.
- **Fayllar:** EMR ilovalari `Storage` interfeysi orqali (`STORAGE_BACKEND=local`, docker volume `uploads`, `MAX_UPLOAD_MB`); tur baytlar bo'yicha aniqlanadi.
- **Frontend:** demo/zaxira ma'lumot yo'q; xatoda toast + "Qayta urinish", bo'sh ro'yxatda `EmptyState`. Chat va Obuna sahifalari yashirilgan (`hidden`, kodi bor).

## Reja: 6 bosqich

**1-bosqich: Ma'lumot asosi (v1.5.x): TUGADI (v1.5.15).** app/ tuzilmasi, PostgreSQL + Alembic, sxema, seed, rollar/ruxsatlar bazada, audit va sessiyalar,
analitika bazadan, demo olib tashlandi, pytest + ruff + eslint + GitHub Actions.

### 2-bosqich: Klinik yadro (v1.6.x): TUGADI (v1.6.15)
Bemor (PINFL, telefon/sana qidiruvi, ism normallashtirish `name_norm`, dublikatlarni topish va `patients:merge` bilan birlashtirish),
shifokor jadvali (haftalik shablon + istisnolar, qabul turi bo'yicha davomiylik, kabinetlar, bo'sh vaqtlar, kutish ro'yxati,
bir vaqtga ikkita qabul bazadagi exclusion cheklov bilan taqiqlangan), EMR (MKB-10, ko'rik bo'limlari va shablonlar,
INN retsept, DMED tartibidagi ko'rik kartasi, nusxalash, PDF, qo'lda "ko'chirildi" belgisi), laboratoriya (katalog, jins/yosh
me'yori, buyurtma, natija belgisi, PDF). **Shart** `backend/tests/test_e2e_stage2.py` bilan isbotlangan.

### 3-bosqich: Moliya va kassa (v1.7.x): TUGADI (v1.7.8)
Narxnoma (MXIK/package_code/QQS; kodsiz xizmat sotilmaydi), hisob-faktura (chegirma, QQS), to'lov (naqd, karta, Payme Merchant API,
Click Prepare/Complete), fiskal chek adapteri (mock), qaytarish, shifokor foizi (qoidalar, oylik hisob, teskari yozuv), kassa smenasi
(X/Z-hisobot). **Shart** (har bir to'lov chek bilan yopiladi, mock'da chek ID) `backend/tests/test_e2e_stage3.py` bilan isbotlangan.
Frontend: Kassa (`/cashier`) va Shifokor foizi (`/commissions`) sahifalari, Sozlamalar > Narxnoma.

### 4-bosqich: Bemor bilan aloqa (v1.8.x): TUGADI (v1.8.8)
Celery + Redis (worker, beat: backend imajidan), SMS (mock) va Telegram adapterlari, kanal bo'yicha rozilik, eslatmalar 24 va 2 soat oldin
(tungi 21:00-08:00 ertalabga suriladi, 3 marta qayta urinish), imzolangan muddatli tasdiqlash/bekor havolalari (bekor bo'lsa vaqt kutuvchiga taklif),
xabarlar logi, onlayn yozilish (OTP, tezlik cheklovi, honeypot), bemor portali (`/portal/*`, faqat shifokor tasdiqlagan lab natijasi, EMR matni yo'q),
Telegram bot (`app/bot.py`, profil `bot`), bemor manbasi va qayta tashrif eslatmasi. **Shart** (haftalik kelmay qolish ulushi Dashboard'da,
eslatmali/eslatmasiz) `backend/tests/test_e2e_stage4.py` bilan isbotlangan.
- Qarorlar: tranzaksion OTP rozilik va tungi vaqtdan mustasno; rozilik navbatga qo'yishda ham, yuborishda ham tekshiriladi; havola/OTP HMAC (`LINK_SECRET`);
  ochiq oqimlar `SystemActor` (ruxsatsiz, `created_by` null); tibbiy ma'lumot Telegram'da faqat telefon tasdiqlangach.
- Env: `REDIS_URL`, `PUBLIC_BASE_URL`, `SMS_BACKEND=mock`, `TELEGRAM_BOT_TOKEN`, `LINK_SECRET`.
- Biznes qarorlari (v1.7.9-v1.7.13): chegirma limiti (`finance:discount_override`), foiz asosi standart "chegirmadan keyin, QQS'siz" (Sozlamalar),
  foiz to'lov hujjati (Draft/Approved/Paid), inkassatsiya (`finance:cash_withdrawal`), Click qaytarishi naqd/karta bilan.
- Ochiq: haqiqiy SMS provayder adapteri va Telegram token. (Portal sahifasi v1.8.10, LabView tasdiqlash v1.8.9, Playwright e2e v1.8.11 da qilindi.)

### 5-bosqich: Ombor va filiallar (v1.9.x): TUGADI (v1.9.14)
Ombor: katalog (`stock_items`, dori/sarf, minimal qoldiq), kirim hujjati va partiyalar (partiya raqami, yaroqlilik muddati, kirim narxi), harakatlar jurnali
(faqat qo'shiladi), FEFO chiqim, hisobdan chiqarish, 30 kunlik yaroqlilik ogohlantirishi, xizmat sarf normasi va avtomatik tannarx, to'lovda avtomatik sarf,
filiallar orasida ko'chirish hujjati. Filiallar: CRUD, foydalanuvchi filialga biriktiriladi, faol filialni almashtirish (`X-Branch-Id`), ro'yxatlar/kassa/ombor/hisobot
filial bo'yicha. Frontend: Ombor sahifasi, filial almashtirgich, Sozlamalar > Filiallar, narxnomada sarf normasi va tannarx, Dashboard (hamma filial, ombor kartasi).
**Shart** (xizmat tannarxi sarf materiallar bilan avtomatik hisoblanadi) `backend/tests/test_e2e_stage5.py` bilan isbotlangan.
- Qarorlar: katalog hamma filialga umumiy, qoldiq filial bo'yicha partiyalarda; miqdor `numeric(14,3)`, narx `numeric(14,2)`; harakatlar jurnali yig'indisi = partiya qoldig'i (testda tekshiriladi);
  FEFO: muddati bo'yicha, muddatsiz oxirida, muddati o'tgan ishlatilmaydi, yetmasa 409 (qisman emas); kirimda muddati o'tgan tovar va kelajak sanasi rad etiladi.
- Tannarx = norma x material narxi: ombordagi yaroqli qoldiqning o'rtacha tortilgan narxi, qoldiq yo'q bo'lsa oxirgi kirim narxi, kirim yo'q bo'lsa noma'lum (`complete=false`). Foyda QQS'siz narxdan.
- Avtomatik sarf: xizmat BAJARILGANDA (v1.9.15; to'lovda emas): qabul `Completed` bo'lganda bog'langan hisob-faktura qatorlari, yoki qator qo'lda `POST /invoices/{id}/lines/{line}/perform` (`appointments:write`);
  `invoice_lines.performed_at`, bir marta. Xato belgilangan bo'lsa `DELETE .../perform`: sarf o'z partiyalariga qaytadi (`Return`); bajarilgan xizmat pulini qaytarish materialni qaytarmaydi.
  Ombor yetmasa to'lov va bajarish to'xtamaydi, qoldiq manfiyga tushmaydi: `stock_shortages`, kirimdan keyin `resolve`.
- Ko'chirish: yuborilganda manba FEFO bo'yicha kamayadi (`Sent`), qabul qiluvchi filial `receive` qilsa o'z partiyasi (xuddi shu raqam, muddat, narx) ochiladi; qabulgacha yuboruvchi bekor qila oladi.
- Filial: foydalanuvchi bitta filialda (`users.branch_id`, `staff.branch_id`); `X-Branch-Id` faqat `branches:all` (admin); bemor bazasi umumiy, bemor tarixi (`patient_id` bilan uchrashuv/EMR/lab) filialdan qat'i nazar ko'rinadi;
  faolsizlantirish: asosiy filial, faol xodimi, ombor qoldig'i yoki hozirgi faol filial bo'lsa 409. Hisobotlar `all_branches=true` (faqat `branches:all`).
- Ruxsatlar: `warehouse:read/write/transfer`, `branches:manage/all` (data migratsiya admin/hamshiraga beradi).
- **Qarorlar (foydalanuvchi, 2026-11-14), 6-bosqichdan oldin bajariladi:** (1) sarf xizmat bajarilganda [v1.9.15 TAYYOR]; (2) yetishmovchilik: ombor mas'uliga ogohlantirish (bildirishnoma); (3) shifokor bir nechta filialda
  ishlaydi: jadval shablonlari va istisnolar filial bo'yicha, bir vaqtda ikki filialda jadval taqiqlanadi; (4) onlayn yozilish va bemor portalida filial tanlash; (5) inventarizatsiya (sanoq hujjati, farq bo'yicha
  avtomatik kirim/chiqim, ruxsat bilan tasdiq), ko'chirishda qisman qabul, filial bo'yicha narx (asosiy narxdan farqli bo'lishi mumkin).
- **6-bosqich qarorlari:** versiyalar v1.9.x davom etadi, `v2.0.0` bosqich oxirida. 1C: rasmiy format hujjati yo'q, universal eksport (sotuvlar xizmat bo'yicha, to'lovlar usul bo'yicha, kassa smenalari, ombor harakatlari,
  shifokor foizlari), Excel va CSV, davr va filial filtri, ustun xaritasi Sozlamalarda tahrirlanadi (keyin buxgalter bilan 1C ga moslanadi). Sug'urta: faqat ixtiyoriy tibbiy sug'urta (DMS), davlat jamg'armasi yo'q;
  sug'urta kompaniyasi -> shartnoma (muddat, chegirma, qoplanadigan xizmatlar, limitlar) -> bemor polisi (raqam, muddat, kompaniya) -> kafolat xati (raqam, sana, summa limiti, xizmatlar, fayl ilovasi);
  hisob-fakturada summa bemor va sug'urta ulushiga bo'linadi; oyiga kompaniya bo'yicha reyestr (Excel) va qarzdorlik hisobi. AI: `AI_ENABLED` orqali lokal LLM (OpenAI-mos), qayd xulosasi, shifokor tasdiqlamaguncha saqlanmaydi. Ochiq REST API hujjati.

### 6-bosqich: Analitika va AI (v2.0.0)
- Hisobotlar: daromad, bemor oqimi, shifokor yuklamasi, kelmay qolish; PDF/Excel va 1C eksporti.
- AI_ENABLED=true bo'lganda lokal LLM bilan qayd xulosasi; shifokor tasdiqlamaguncha saqlanmaydi.
- Sug'urta kompaniyalari: polis, kafolat xati, oylik hisob.
- Boshqa tizimlar uchun ochiq REST API hujjati.

Har bosqich: bitta band = bitta commit = bitta versiya, CHANGELOG, tag, push; oxirida "Shart"ni test yoki skript bilan isbotlab hisobot.

## Ochiq masalalar

- **3-bosqich real kalit/hujjat kutadi (hozir mock/test):** (1) Payme merchant ID va kalit: sandbox'da sinash, `PAYME_UNITS_CODE=796` (dona) taxmin;
  (2) Click service_id/merchant_id/secret: sandbox'da sinash, Click to'lovini qaytarish (reverse) API yozilmagan; (3) fiskal chek: real virtual kassa
  operatori adapteri (`services/fiscal.py`, hozir faqat `MockFiscalAdapter`); (4) `package_code` formati (1-10 raqam) va MXIK faqat uzunlik/raqam bilan tekshiriladi;
  (5) QQS stavkasi kodlanmagan (narxnomada xizmat bo'yicha).
- Biznes taxminlari (tasdiqlash kerak): `finance:discount` kassirga ham berilgan; shifokor foizi asosi standart "QQS bilan to'langan summa";
  oy yopilganda foiz to'lovi (chiqim) yozilmaydi; kassaga kirim/chiqim (inkassatsiya) yo'q; ish vaqtidan tashqari yozish `appointments:override` bilan.

- **Starter ma'lumotnomalar rasmiy emas** (muallif yozgan, shifokor/laboratoriya tekshirishi shart): `backend/data/mkb10_starter.csv`
  (142 toifa), `inn_starter.csv` (146), `lab_starter.json` (24 tahlil, kattalar 18+ me'yori). To'liq rasmiy fayl:
  `docker compose exec backend python scripts/import_mkb10.py <csv>` / `scripts/import_inn.py <csv>`; tahlil me'yorlari Sozlamalar/API orqali.
- **DMED ko'rik kartasi maydon tartibi taxminiy** (DMED shakli hujjati yo'q edi): haqiqiy shakl bilan solishtirib `services/emr_card.py` ni tuzatish.
- Ish vaqtidan tashqari qabul yozish faqat jadvalni o'zgartirish orqali mumkin (admin uchun "majburan yozish" yo'q).
- Eski EMR formasida (EMRView) simptom chiplari, fayl ilovalari saqlanmaydi (backendda yo'q); qayta ishlash kerak.
- Kutish ro'yxati bildirishnomalari 4-bosqichda (SMS/Telegram).

- Sozlamalar (Klinika "Saqlash"), sessiyani bekor qilish va parol o'zgartirish UI'lari qo'lda tekshirilmoqda (backend testlangan, UI to'liq sinalmagan).
- Dashboard'da AI sahifasiga olib boradigan tugma yo'q (menyuda "AI" bor).
- Push `.github/workflows/ci.yml` o'zgarishi bilan rad etilgan edi (`workflow` scope yo'q, v1.5.19 lokal): foydalanuvchi `gh auth refresh -h github.com -s workflow` bajargach push qilinadi.
- GitHub Actions'da Node 20 deprecation ogohlantirishi bor (action versiyalarini keyin yangilash).
- Prettier yo'q (faqat eslint). `v1.5.5` API'ni buzgan edi (MAJOR bo'lishi kerak edi), `v1.5.x` raqamlash saqlandi.
- Uchrashuvda bemor hali ism bo'yicha topiladi (`AppointmentsView`); bir vaqtga ikkita qabul cheklovi 2-bosqichda.
- Audit eksporti yo'q. Refresh token bekor qilinsa ham amaldagi access token <=30 daqiqa ishlaydi.
