# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versiyalash: [SemVer](https://semver.org/).

## [1.5.0] - 2026-11-03
### Changed
- `backend/main.py` `app/` tuzilmasiga bo'lindi: `core/` (config, security), `schemas/`, `routers/`, `services/`, `db/`. API yo'llari o'zgarmadi. Sozlamalar `pydantic-settings` orqali (1-bosqich, band 1).

## [1.4.7] - 2026-11-03
### Added
- Umumiy toast komponenti (`AppToast`, `useToast`); FastAPI xatolari (jumladan 422) o'qiladigan ko'rinishda.
### Fixed
- `.catch(() => {})` bilan xatolarni yutish olib tashlandi (bemorlar, xodimlar, uchrashuvlar, EMR, sozlamalar). Optimistic update o'rniga server javobi ishlatiladi; uchrashuv statusi xatoda rollback qilinadi (band 9).
- Uchrashuv har doim `patient_id: '1'` bilan yaratilardi: endi bemor nomi bo'yicha haqiqiy ID topiladi. EMR ham haqiqiy bemorlar ro'yxatidan tanlaydi va `patient_id`/`prescription` yuboradi. Bemor `age` songa o'giriladi.
- Ma'lumot yuklashdagi xatolar toast bilan ko'rsatiladi (demo fallback hozircha saqlangan).

## [1.4.6] - 2026-11-03
### Fixed
- ID generatsiyasi `len()+1` o'rniga UUID: o'chirishdan keyin yangi yozuv mavjud ID bilan to'qnashmaydi (band 10).

## [1.4.5] - 2026-11-03
### Changed
- Pydantic v2: `.dict()` -> `.model_dump()`, `Field(example=...)` -> `Field(examples=[...])` (band 11).

## [1.4.4] - 2026-11-03
### Added
- `GET /appointments?patient_id=` filtri: bemor profili faqat o'z uchrashuvlarini ko'rsatadi (band 7).

## [1.4.3] - 2026-11-03
### Added
- `PUT /staff/{id}` (`StaffUpdate`: faqat yuborilgan maydonlar yangilanadi, topilmasa 404) (band 6).

## [1.4.2] - 2026-11-03
### Fixed
- `FinanceView` `/patients?limit=200` backend `le=100` tufayli 422 berardi (band 5). Frontend endi sahifalab oladi (`fetchAll`); `PatientsView` ham (100 dan ko'p bemor jimgina kesilardi).

## [1.4.1] - 2026-11-03
### Added
- `GET /reports/download/{id}`: CSV (UTF-8 BOM, Excel to'g'ri ochadi; formula-injection himoyasi). Frontend CSV'ni yuklab oladi, xato bo'lsa halol ko'rsatadi (2-bosqich, band 8).
### Changed
- `forgot-password`: backend 501, UI'da "Parolni tiklash uchun administratorga murojaat qiling".

## [1.4.0] - 2026-11-03
### Added
- Refresh token (7 kun, `REFRESH_TOKEN_EXPIRE_DAYS`) va `POST /auth/refresh` (access 30 daqiqa, refresh token aylantiriladi). Tokenlarda `type` maydoni: refresh token API uchun access sifatida o'tmaydi.
- Frontend: 401 da avval refresh qilib, so'rovni qayta yuboradi; refresh ham o'tmasagina `/login` ga yo'naltiradi.

## [1.3.0] - 2026-11-03
### Added
- `AI_ENABLED` flag (standart `false`). O'chiq bo'lsa `/ai/chat` va `/ai/analyze` tashqi so'rov yubormaydi, statik demo javoblar va disclaimer qaytaradi. `GET /ai/status`, javoblarda `demo` maydoni.
- Frontend: AI Yordamchi va Analytics AI blokida "Demo rejim" belgisi; 503 xatosi ko'rinmaydi.
### Changed
- LLM integratsiya kodi saqlandi, faqat flag bilan o'chiriladi.

## [1.2.2] - 2026-11-02
### Security
- CORS: `allow_origins` `CORS_ORIGINS` env'dan (vergul bilan), `*` ruxsat etilmaydi; metod va header'lar cheklandi.

## [1.2.1] - 2026-11-02
### Security
- Parol xeshi MD5 o'rniga bcrypt. Demo foydalanuvchi (admin@clinic.uz) saqlandi.

## [1.2.0] - 2026-11-02
### Added
- Haqiqiy JWT (PyJWT, HS256): `JWT_SECRET` env'dan, access token 30 daqiqa. `get_current_user` tokenni tekshiradi; noto'g'ri/eskirgan token → 401.
### Changed
- `JWT_SECRET` majburiy (kamida 32 belgi), bo'lmasa backend ishga tushmaydi.

## [1.1.0] - 2026-11-02
### Security
- AI so'rovlari backend orqali: `POST /ai/chat`, `POST /ai/analyze`. Frontend LLM kalitini bilmaydi.
- LLM sozlamalari env'dan (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT`), OpenAI-mos har qanday API ishlaydi.
- Xatolar: 503 (sozlanmagan), 504 (timeout), 502 (LLM xatosi). Tibbiy disclaimer saqlandi.

## [1.0.0] - 2026-11-02
### Added
- Dastlabki import: FastAPI backend, Vue 3 frontend, Docker Compose.

### Security
- Frontend kodidan Groq API kaliti olib tashlandi; AI so'rovlari vaqtincha o'chirilgan.
