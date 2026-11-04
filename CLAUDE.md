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
- Repo: github.com/Davronkhuja/Digital-Clinic (shaxsiy, `origin`, branch `main`).
- Til: foydalanuvchi bilan va UI/commit/CHANGELOG matnlarida o'zbekcha.

## Ish qoidalari

1. **Bitta band = bitta commit = bitta versiya (SemVer)**: xato tuzatish PATCH, yangi imkoniyat yoki ichki qayta qurish MINOR,
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

## Buyruqlar

```bash
docker compose up -d --build                           # hammasi
docker compose --profile test run --rm --build test    # pytest (alohida <POSTGRES_DB>_test bazasi)
ruff check backend                                     # backend lint
cd frontend && npm run lint && npm run build           # frontend lint va build
docker compose exec backend alembic revision --autogenerate -m "..." --rev-id NNNN   # migratsiya; faylni docker cp bilan chiqarib ol
```

CI: `.github/workflows/ci.yml` (lint -> pytest -> frontend build -> docker build). `gh run list` / `gh run watch` bilan kuzat.

Lokal `.env`da `SEED_DEMO=true` (demo hisoblar, parol `password123`: `admin@clinic.uz`, `rustamov@clinic.uz` doctor,
`yusupova@clinic.uz` nurse, `mirzayev@clinic.uz` receptionist, `akbarova@clinic.uz` cashier). `.env` gitda yo'q.
Brauzer sinovi uchun: login API'dan token olib `localStorage` (`token`, `refresh_token`, `user`) ga yoz, sahifani qayta yukla.

## Backend tuzilmasi

`backend/app/`: `main.py`, `core/` (config = pydantic-settings, security = JWT/bcrypt, deps = `get_current_user`, `require("perm")`,
permissions = ruxsatlar katalogi va standart rollar), `db/` (base, session), `models/`, `schemas/`, `routers/<bo'lim>.py`,
`services/` (queries = join bilan ro'yxatlar, serializers, audit, auth, analytics, periods, llm, lookup), `seed.py`. Migratsiyalar: `backend/alembic/versions/`.

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
- **Frontend:** demo/zaxira ma'lumot yo'q; xatoda toast + "Qayta urinish", bo'sh ro'yxatda `EmptyState`. Chat va Obuna sahifalari yashirilgan (`hidden`, kodi bor).

## Reja: 6 bosqich

**1-bosqich: Ma'lumot asosi (v1.5.x): TUGADI (v1.5.15).** app/ tuzilmasi, PostgreSQL + Alembic, sxema, seed, rollar/ruxsatlar bazada, audit va sessiyalar,
analitika bazadan, demo olib tashlandi, pytest + ruff + eslint + GitHub Actions.

### 2-bosqich: Klinik yadro (v1.6.x)
- Bemor: PINFL tekshiruvi, telefon va sana bo'yicha qidiruv, dublikatlarni birlashtirish.
- Shifokor jadvali (ish kunlari, soatlar, tanaffus), bo'sh vaqtlar, kutish ro'yxati, kabinetlar.
  Bir vaqtga ikkita qabul yozib bo'lmasin.
- EMR: MKB-10 ma'lumotnomasi (import skripti), ko'rik shablonlari (shikoyat, anamnez, ko'rik, tashxis, tavsiya), INN bo'yicha retsept (doza, usul, muddat).
- Laboratoriya: buyurtma, natija shablonlari, me'yor bilan solishtirish, PDF.
- Ko'rik kartasi DMED maydonlari tartibida bo'ladi. MKB-10, INN va dozani bir tugma bilan nusxalash, chop etish,
  qo'lda qo'yiladigan "DMED ga ko'chirildi" belgisi (API yo'q).
- **Shart:** bitta qabul yozilishdan retseptgacha qog'ozsiz o'tadi (e2e test).

### 3-bosqich: Moliya va kassa (v1.7.x)
- services (narxnoma, kategoriyalar), invoices, payments (naqd, karta, Click, Payme), chegirmalar, qaytarish, kassa smenasi (ochish/yopish, Z-hisobot).
- Shifokor foizi: xizmat va shifokor bo'yicha foiz yoki qat'iy summa, oylik hisob-kitob.
- Fiskal chek adapteri (virtual kassa), Click va Payme adapterlari: avval mock interfeys bilan.
  Real API hujjatlari bo'lmasa, mock'da to'xta va so'ra.
- **Shart:** har bir to'lov chek bilan yopiladi (mock'da chek ID saqlanadi).

### 4-bosqich: Bemor bilan aloqa (v1.8.x)
- Celery + Redis. Eslatmalar qabuldan 24 soat va 2 soat oldin, SMS va Telegram orqali; tasdiqlash va bekor qilish havolasi.
  SMS shlyuzi adapter orqali (avval mock).
- Telegram bot: yozilish, eslatma, natijani olish.
- Onlayn yozilish sahifasi va bemor portali (o'zbek, rus).
- Bemor manbasi (reklama, tavsiya, Instagram), qayta tashrif eslatmasi.
- **Shart:** kelmay qolish ulushi har hafta hisoblanib, Dashboard'da ko'rinadi.

### 5-bosqich: Ombor va filiallar (v1.9.x)
- Dori va sarf materiallar: kirim, qoldiq, minimal qoldiq ogohlantirishi, xizmatga bog'langan sarf, tannarx.
- Filiallar: umumiy bemor bazasi, filial bo'yicha jadval, kassa va hisobot, foydalanuvchi filialga bog'lanadi.
- **Shart:** xizmat tannarxi sarf materiallar bilan avtomatik hisoblanadi.

### 6-bosqich: Analitika va AI (v2.0.0)
- Hisobotlar: daromad, bemor oqimi, shifokor yuklamasi, kelmay qolish; PDF/Excel va 1C eksporti.
- AI_ENABLED=true bo'lganda lokal LLM bilan qayd xulosasi; shifokor tasdiqlamaguncha saqlanmaydi.
- Sug'urta kompaniyalari: polis, kafolat xati, oylik hisob.
- Boshqa tizimlar uchun ochiq REST API hujjati.

Har bosqich: bitta band = bitta commit = bitta versiya, CHANGELOG, tag, push; oxirida "Shart"ni test yoki skript bilan isbotlab hisobot.

## Ochiq masalalar

- Sozlamalar (Klinika "Saqlash"), sessiyani bekor qilish va parol o'zgartirish UI'lari qo'lda tekshirilmoqda (backend testlangan, UI to'liq sinalmagan).
- Dashboard'da AI sahifasiga olib boradigan tugma yo'q (menyuda "AI" bor).
- Prettier yo'q (faqat eslint). `v1.5.5` API'ni buzgan edi (MAJOR bo'lishi kerak edi), `v1.5.x` raqamlash saqlandi.
- Uchrashuvda bemor hali ism bo'yicha topiladi (`AppointmentsView`); bir vaqtga ikkita qabul cheklovi 2-bosqichda.
- Audit eksporti yo'q. Refresh token bekor qilinsa ham amaldagi access token <=30 daqiqa ishlaydi.
