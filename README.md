# Digital Clinic

Xususiy klinikalar uchun boshqaruv tizimi: bemorlar, uchrashuvlar, EMR, moliya, tahlil, rollar va audit.

- **Backend:** FastAPI + SQLAlchemy 2 + Alembic, PostgreSQL 16 (`backend/`)
- **Frontend:** Vue 3 + Vite + Pinia + Tailwind (`frontend/`), nginx orqali `/api` backendga proksilanadi
- **Ishga tushirish:** Docker Compose

## Tez boshlash

```bash
cp .env.example .env
# .env ni to'ldiring (pastga qarang): POSTGRES_PASSWORD, JWT_SECRET, SEED_DEMO yoki ADMIN_*
docker compose up -d --build
```

| Xizmat | Manzil |
|---|---|
| Ilova (frontend) | http://localhost:5180 |
| API / Swagger | http://localhost:8010/docs |
| PostgreSQL | faqat compose tarmog'ida (host portiga ochilmagan) |

Konteyner ishga tushganda `alembic upgrade head` va `python -m app.seed` avtomatik bajariladi.

### Birinchi kirish

- **Lokal ishlash:** `.env` da `SEED_DEMO=true` qiling. Bo'sh bazaga demo ma'lumotlar va demo hisoblar yuklanadi
  (`admin@clinic.uz`, `rustamov@clinic.uz` (doctor), `yusupova@clinic.uz` (nurse), `mirzayev@clinic.uz` (receptionist),
  `akbarova@clinic.uz` (cashier); parol hammasida `password123`). **Productionda hech qachon.**
- **Production:** `SEED_DEMO=false` (standart) va `ADMIN_EMAIL` / `ADMIN_PASSWORD` (kamida 10 belgi) bering.
  Bazada foydalanuvchi bo'lmasa va bular berilmasa, backend ishga tushmaydi.
  Ochiq ro'yxatdan o'tish yo'q: xodim va loginlarni administrator Sozlamalar → Foydalanuvchilar orqali qo'shadi.

## Muhit o'zgaruvchilari (`.env`)

| O'zgaruvchi | Tavsif |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Ma'lumotlar bazasi (compose `DATABASE_URL` ni o'zi yig'adi) |
| `JWT_SECRET` | Kamida 32 belgi (`openssl rand -hex 32`); bo'lmasa backend ishga tushmaydi |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | 30 daqiqa / 7 kun |
| `CORS_ORIGINS` | Vergul bilan ajratilgan aniq originlar (`*` mumkin emas) |
| `SEED_DEMO`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Boshlang'ich ma'lumotlar (yuqoriga qarang) |
| `AI_ENABLED` | `false` (standart): AI demo rejimida, tashqi so'rov yo'q. `true` bo'lsa `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` kerak (OpenAI-mos API) |
| `TRUSTED_PROXIES` | Mijoz IP'sini `X-Forwarded-For` dan olishga ishonchli proksilar (audit uchun) |

Sirlarni (parol, kalit, JWT secret) hech qachon commit qilmang: ular faqat `.env` da, repoda faqat `.env.example`.

## Rollar

admin, doctor, nurse, receptionist, cashier. Ruxsatlar bazada saqlanadi va Sozlamalar → Rollar sahifasida
o'zgartiriladi (administrator roli o'zgarmaydi). Backend har endpointda ruxsatni tekshiradi, frontend menyuni yashiradi.

## Testlar va lint

```bash
docker compose --profile test run --rm --build test   # pytest, alohida <POSTGRES_DB>_test bazasida
ruff check backend                                    # backend lint
cd frontend && npm run lint && npm run build          # frontend lint va build
```

GitHub Actions (`.github/workflows/ci.yml`): lint → test → frontend build → docker build.

## Versiyalash

[SemVer](https://semver.org/): xato tuzatish = PATCH, yangi imkoniyat yoki ichki qayta qurish = MINOR,
API'ni buzadigan o'zgarish = MAJOR. Versiya bir vaqtda uch joyda yangilanadi: `VERSION`, `frontend/package.json`,
`backend/app/__init__.py` (`__version__`). Har versiya `CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com/)),
Conventional Commits va `vX.Y.Z` tegi bilan chiqadi.

## Ma'lumotlar xavfsizligi bo'yicha eslatma

EMR, retsept va to'lov yozuvlari hech qachon o'chirilmaydi (`deleted_at`). Bemor, EMR va to'lov yozuvlarini
o'qish/yozish `audit_log` ga yoziladi (kim, qachon, nima, IP). Refresh tokenlar bazada saqlanadi va
logout, parol o'zgarishi yoki sessiyani bekor qilishda bekor qilinadi (amaldagi access token ≤30 daqiqa ishlashi mumkin).
