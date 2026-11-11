# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versiyalash: [SemVer](https://semver.org/).

## [1.6.9] - 2026-11-12
### Added
- EMR (1/4): MKB-10 ma'lumotnomasi (`icd10_codes`, migratsiya 0009). `GET /icd10?search=` (kod boshi, o'zbekcha yoki inglizcha nom), `GET /icd10/{code}` (`emr:read`).
- Import skripti `backend/scripts/import_mkb10.py <fayl.csv>` (ustunlar: `code,name_uz[,name_en]`; idempotent upsert, noto'g'ri qatorlar o'tkazib yuboriladi). Bo'sh ma'lumotnomaga `data/mkb10_starter.csv` (142 ta uch belgili toifa) avtomatik yuklanadi.
- **Starter to'plam rasmiy MKB-10 emas**: nomlar muallif tomonidan yozilgan, shifokor tekshirishi shart; to'liq rasmiy fayl skript bilan yuklanadi (ochiq masala).
- `POST /emr`: `icd_code` normallashadi (katta harf), formati va ma'lumotnomada borligi tekshiriladi (I10.9 uchun toifa I10), aks holda 422.
- Frontend: EMR formasida MKB-10 avtoto'ldirish (`Icd10Input`).

## [1.6.8] - 2026-11-11
### Added
- Shifokor jadvali (4/5): kutish ro'yxati (`waitlist`, migratsiya 0008): bemor + shifokor + qabul turi + xohlagan sana oralig'i. Bir bemor bir shifokorni bir vaqtda bir marta kutadi (qisman unikal indeks, 409).
- `GET /waitlist` (FIFO; `status`, `doctor_id`, `for_date`: shu sanani xohlovchilar, masalan bekor bo'lgan qabul o'rniga), `POST /waitlist`, `PATCH /waitlist/{id}` (oraliq, izoh, bekor qilish), `GET /waitlist/{id}/suggestions` (eng yaqin bo'sh vaqtlar), `POST /waitlist/{id}/book` (qabulga yozish: oddiy qoidalar, bitta tranzaksiyada `Booked`; ish vaqti 422, band 409 bo'lsa yozuv `Waiting` qoladi).
- `services/booking.py`: qabul qoidalari (`build_appointment`) va band vaqt -> 409 (`booking_conflicts`) umumiy; qabul yozish va kutish ro'yxatidan yozish bir xil mantiq.
- Frontend: Uchrashuvlar sahifasida "Kutish ro'yxati" bo'limi (qo'shish, vaqt tanlash va yozish, bekor qilish). Bildirishnoma yuborish 4-bosqichda.

## [1.6.7] - 2026-11-11
### Added
- Shifokor jadvali (3/5): haftalik shablon (`doctor_schedules`: hafta kuni, ish soatlari, tanaffus) va istisnolar (`schedule_exceptions`: `Vacation`, `Sick`, `DayOff` oralig'i; `ExtraWork` bir kunlik, o'z soatlari va tanaffusi bilan). Ustuvorlik: `ExtraWork` > ta'til/kasallik/dam olish > shablon. Vaqtlar klinika devor soati (takrorlanuvchi shablon), qabullar timestamptz.
- `GET/PUT /staff/{id}/schedule`, `POST/DELETE /staff/{id}/schedule/exceptions` (o'qish `staff:read`, yozish `staff:write`). Istisno javobida `affected_appointments`: shu davrda ish vaqtidan tashqarida qolgan rejalashtirilgan qabullar (avtomatik bekor qilinmaydi).
- Qabul yozish va ko'chirish ish oynasi ichida bo'lishi shart (422): tanaffus, dam olish kuni, ta'til hisobga olinadi. Shablon umuman belgilanmagan shifokor cheklovsiz (istisnolar baribir amal qiladi).
- `GET /staff/{id}/slots?date=&type=&duration_min=&step_min=&room_id=`: bo'sh boshlanish vaqtlari (ish oynalari, shifokor va kabinet bandligi, bugun uchun o'tgan vaqtlar chiqmaydi).
- Demo seed: 3 shifokor uchun jadval (13:00-14:00 tanaffus). Migratsiya 0007 mavjud bazaga jadval qo'shmaydi.
- Frontend: Xodimlar > "Ish jadvali" (shablon, standart davomiylik va kabinet, istisnolar), qabul formasida bo'sh vaqt tugmalari.

## [1.6.6] - 2026-11-11
### Added
- Shifokor jadvali (2/5): kabinetlar (`rooms`, nomi filial ichida registrsiz unikal; `GET/POST/PUT/DELETE /rooms`, yozish `settings:write`, ishlatilgan kabinet faolsizlantiriladi), shifokorning standart kabineti (`staff.default_room_id`), uchrashuvda `room_id`/`room`.
- Bir vaqtga ikkita qabul yozib bo'lmaydi: bazadagi exclusion cheklovlar (`btree_gist`, `tstzrange` yarim ochiq oraliq) shifokor (`no_doctor_overlap`) va kabinet (`no_room_overlap`) bo'yicha; faqat `Scheduled`/`Completed` band, bekor qilingan va kelmaganlar bo'sh. To'qnashuvda 409 (poyga holatida ham: 6 parallel so'rovdan faqat bittasi o'tadi, test bilan).
- `PATCH /appointments/{id}`: ko'chirish/o'zgartirish (faqat `Scheduled`), shifokor almashsa yangi shifokorning kabineti. Statusni qayta `Scheduled` qilish ham to'qnashuvni tekshiradi.
- Migratsiya 0006 (`CREATE EXTENSION btree_gist`: DB foydalanuvchisi superuser bo'lishi kerak, docker compose'da shunday).
- Frontend: Sozlamalar > "Kabinet va qabul turlari" (qo'shish, tahrirlash, faolsizlantirish), qabul formasida kabinet, jadvalda kabinet ustuni.

## [1.6.5] - 2026-11-11
### Added
- 2-bosqich, shifokor jadvali (1/5): uchrashuv vaqti `timestamptz` (`starts_at`/`ends_at`, UTC); klinika vaqti (Asia/Tashkent) faqat ko'rsatishda. API `date`/`time` saqlanadi, qo'shimcha `end_time`, `duration_min`, `starts_at`. Sana filtri va tahlil klinika kuni bo'yicha (kechasi 00:30 oldingi UTC kuniga tushmaydi).
- Qabul turlari (`appointment_types`, nomi registrsiz unikal) va davomiyligi: `GET/POST/PUT/DELETE /appointment-types` (yozish: `settings:write`; ishlatilgan tur faolsizlantiriladi). Davomiylik ustuvorligi: so'rovdagi `duration_min` -> tur -> `staff.slot_minutes` (shifokor standarti, standart 30) -> 30.
- Migratsiya 0005: eski `date`+`time` -> `starts_at`/`ends_at` (davomiylik tur bo'yicha), `date`/`time` ustunlari olib tashlandi (ORM da `Appointment.date`/`.time` hybrid, klinika vaqti bo'yicha).
- Frontend: qabul turlari API'dan, jadvalda tugash vaqti va davomiylik.

## [1.6.4] - 2026-11-11
### Added
- `patients.name_norm` (indekslangan, migratsiya 0004 mavjud bemorlarni to'ldiradi): ism kirill -> lotin (o'zbek translit: ў=o', қ=q, ғ=g', ҳ=h), `ʻ ʼ ' ` ’ ‘` bitta `'` ga, registrsiz, `ay/ey` oralig'idagi `y` tushirilib (Абдуллаев ~ Abdullayev). Yaratish/o'zgartirishda avtomatik yangilanadi.
- Dublikat guruhida moslik sababi (`reasons`): `pinfl` (eng kuchli), `phone` (ism+telefon), `birth_date` (ism+sana); guruhlar kuchi bo'yicha tartiblanadi. PINFL unikal bo'lgani uchun hozir `pinfl` sababi amalda chiqmaydi (cheklov olib tashlansa ishlaydi).
- Qidiruv ham `name_norm` bo'yicha: "абдуллаев" lotin yozuvdagi bemorni topadi.
- Test: "Абдуллаев Ўктам" va "Abdullayev O'ktam" bitta guruhda.

## [1.6.3] - 2026-11-11
### Changed
- Birlashtirish uchun alohida `patients:merge` ruxsati (seed: admin va receptionist); `patients:delete` endi talab qilinmaydi. Frontend "Dublikatlar" tabi shu ruxsat bilan ko'rinadi.
- Migratsiya 0003: mavjud bazada ruxsat qo'shiladi va admin hamda receptionist rollariga beriladi (boshqa rollar va admin sozlamalari o'zgarmaydi).

## [1.6.2] - 2026-11-11
### Added
- Bemorlar sahifasida "Dublikatlar" tabi (`PatientDuplicates.vue`): guruhlar ro'yxati, yozuvlarni yonma-yon solishtirish (farqlar ajratiladi), asosiy yozuvni tanlash, tasdiqlash oynasi bilan "Birlashtirish".
- Qidiruv maydonida format ko'rsatmasi (telefon, PINFL, sana); qidiruv endi serverda (300 ms debounce), shuning uchun telefon raqamlari va sana bo'yicha ham ishlaydi.

## [1.6.1] - 2026-11-11
### Added
- `POST /patients/{id}/merge` (`patients:delete`): dublikat bemorning uchrashuv, EMR, retsept va to'lovlari asosiy bemorga ko'chiriladi, asosiy bemorning bo'sh maydonlari (PINFL, tug'ilgan sana, manzil, qon guruhi, allergiya, shifokor) to'ldiriladi. Dublikat o'chirilmaydi: `Inactive` va `merged_into`. Audit: `merge`.
- Migratsiya 0002: `patients.merged_into_id` (FK, `SET NULL`).

## [1.6.0] - 2026-11-11
### Added
- 2-bosqich, bemor: qidiruv telefon raqamlari bo'yicha (`+998 (93) 555-12-34`, `935551234` bir xil topiladi) va tug'ilgan sana bo'yicha (`YYYY-MM-DD`, `DD.MM.YYYY`).
- `GET /patients/duplicates`: bir xil ism va (telefon raqamlari yoki tug'ilgan sana) bo'lgan faol bemorlar guruhlari (birlashtirish v1.6.1 da).
- PINFL tekshiruvi (14 raqam, unikal, null mumkin) avvaldan bor edi: testlar bilan tasdiqlandi.

## [1.5.20] - 2026-11-09
### Changed
- `CLAUDE.md`: HTTPS remote va `gh auth setup-git`, CI qoidalari (tag trigger yo'q, ruff pin), Docker disk ogohlantirishi, `workflow` scope talabi, ochiq masalalar yangilandi.

## [1.5.19] - 2026-11-09
### Changed
- CI: tag push'lari workflow'ni ishga tushirmaydi (har push'da 2-3 ta takroriy run bo'lardi); faqat `main` push va `pull_request`.

## [1.5.18] - 2026-11-04
### Fixed
- Favikon: `index.html` `/favicon.ico` ga ishora qilardi, lekin `frontend/public/` yo'q edi (nginx SPA zaxirasi `index.html` qaytarardi). `public/` yaratildi: `favicon.svg` (yumaloq kvadrat ichida xoch, loyiha asosiy rangida), `favicon.ico` (16/32/48), `apple-touch-icon.png` (180), `icon-192.png`, `icon-512.png`; `index.html` da svg/ico/apple-touch-icon va `theme-color`.

## [1.5.17] - 2026-11-04
### Fixed
- CI: ruff versiyasi CI va `requirements-dev.txt` da bir xil (0.15.22). Avval CI 0.5.5 ni o'rnatgan, `pyproject.toml` esa yangi qoidalarni (`UP045`) ishlatgani uchun lint yiqilgan edi.

## [1.5.16] - 2026-11-04
### Added
- `CLAUDE.md`: loyiha, ish qoidalari, qabul qilingan sxema qarorlari, 2-6 bosqichlar rejasi, ochiq masalalar. `scripts/bump-version.sh` (versiyani uch joyda yangilaydi).

## [1.5.15] - 2026-11-03
### Added
- Frontend: eslint (`npm run lint`, flat config + eslint-plugin-vue); kod lintdan o'tdi.
- GitHub Actions (`.github/workflows/ci.yml`): lint (ruff + eslint) -> pytest (PostgreSQL service) -> frontend build -> docker build.
- README yangilandi: ishga tushirish, env, portlar, rollar, testlar, versiyalash (1-bosqich, band 10 oxiri).

## [1.5.14] - 2026-11-03
### Fixed
- nginx: `index.html` `Cache-Control: no-cache` bilan beriladi; avval brauzer eski `index.html` ni keshlab, yangi deploydan keyin eski sahifa ko'rinardi. Hash'li `assets/` uzoq keshlanishda qoladi.

## [1.5.13] - 2026-11-03
### Changed
- Dashboard va Tahlil sahifalari faqat bazadan hisoblangan raqamlarni ko'rsatadi (`period`: hafta/oy/yil/hammasi): kartalar, oldingi davr bilan o'zgarish, daromad va qabul grafiklari, tashxislar, shifokorlar yuklamasi, yosh/jins/bo'lim taqsimoti, qabul statuslari (bekor qilish va kelmay qolish ulushi). AI tahlili uchun statistika matni haqiqiy ma'lumotdan yig'iladi. `analytics:read` yo'q foydalanuvchiga salomlashuv bloki (1-bosqich, band 8, frontend qismi).
### Removed
- Qattiq yozilgan raqamlar, "AI Tavsiyalar" va "So'nggi faoliyat" demo bloklari, "Bemorlar sog'lig'i 94%", shifokor reytingi, sparklinelar.

## [1.5.12] - 2026-11-03
### Changed
- Chat va Obuna sahifalari menyudan yashirildi; URL orqali ham ochilmaydi (`meta.hidden`). Kodlari saqlangan, yoqish uchun `hidden` belgisini olib tashlash kifoya (1-bosqich, band 9).

## [1.5.11] - 2026-11-03
### Added
- Xavfsizlik sahifasi haqiqiy ma'lumot bilan: audit jurnali (filtr, sahifalash), barcha faol sessiyalar (administrator) va o'z sessiyalari bekor qilish bilan, parolni o'zgartirish (1-bosqich, band 7, frontend qismi).
### Removed
- Qattiq yozilgan xavfsizlik kartalari (shifrlash, firewall, tahdidlar, 2FA holati) va demo audit/sessiya ro'yxatlari.

## [1.5.10] - 2026-11-03
### Added
- Frontend: menyu va marshrutlar ruxsatga qarab (`auth.can(perm)`, router `meta.perm`; ruxsatsiz URL birinchi ruxsat etilgan sahifaga yo'naltiriladi). Ruxsatlar `GET /auth/me` bilan yangilanadi; `logout` refresh tokenni bekor qiladi.
- Sozlamalar: Klinika (`/settings`), Rollar (`/roles`, `/permissions`: ruxsatlarni bazaga yozish; administrator roli o'zgarmaydi), Foydalanuvchilar (`/users`: xodim qo'shish, rol, faollashtirish) (1-bosqich, band 6, frontend qismi).
### Removed
- Login sahifasidagi demo hisob ma'lumotlari bloki va oldindan to'ldirilgan email/parol; Sozlamalardagi qattiq yozilgan rollar va bildirishnomalar.

## [1.5.9] - 2026-11-03
### Changed
- `/analytics/dashboard` va `/analytics/reports` (`period=week|month|year|all`) qattiq yozilgan raqamlar o'rniga bazadan hisoblanadi: jami/yangi bemorlar, bugungi va davr uchrashuvlari, daromad/xarajat, oldingi teng davr bilan o'zgarish foizi, 6 oylik daromad grafigi, 7 kunlik bemor oqimi, eng ko'p tashxislar, shifokorlar yuklamasi, bo'limlar, demografiya (jins, yosh guruhlari). Javob shakli yangilandi (API'ni buzadi: `monthly_revenue` -> `revenue`, `*_change` satrlari -> `changes` raqamlari, `rating` olib tashlandi: ma'lumot yo'q).
- `GET /ai/insights` bazadan hisoblanadi (bekor qilish ulushi, daromad dinamikasi, eng band kun); ruxsat `analytics:read`.
- `period` oynalari aylanma: week=7, month=30, year=365 kun; `/finance/summary` ham shunga o'tdi (Dashboard bilan mos). `all` chegarasiz (1-bosqich, band 8, backend qismi).

## [1.5.8] - 2026-11-03
### Removed
- Frontend demo/zaxira ma'lumotlari: Bemorlar, Bemor profili, Uchrashuvlar, Xodimlar, EMR, Moliya, Hisobotlar sahifalarida qattiq yozilgan ro'yxatlar, shifokor ro'yxatlari, soxta raqamlar, komissiya jadvali, soxta `txn_id`/`method`/`status`, xodimlardagi demo rol va faoliyat tablari (1-bosqich, band 5, qisman).
### Added
- Yuklash xatosida toast va "Qayta urinish" holati; bo'sh ro'yxat uchun `EmptyState` komponenti. Bemor profili boshqa bemorning ma'lumotini hech qachon ko'rsatmaydi ("Bemor topilmadi" holati).
- Shifokorlar `GET /staff?role=Doctor` dan; bemor formasida PINFL; hisobotlar ro'yxati `GET /reports` dan; moliya kartalari `GET /finance/summary?period=` dan.
### Fixed
- EMR yozuvidan o'chirish tugmasi olib tashlandi (yozuvlar o'chirilmaydi); EMR `icd_code` yuboriladi.
- Hali qolgan: Dashboard, Tahlil, Xavfsizlik, Sozlamalar sahifalari (keyingi versiyalarda).

## [1.5.7] - 2026-11-03
### Added
- Audit jurnali: bemor, EMR, to'lov yozuvlarini o'qish/yozish, hisobot yuklab olish, kirish (muvaffaqiyatli va muvaffaqiyatsiz), chiqish, parol o'zgarishi, rol va foydalanuvchi o'zgarishlari: kim, qachon, nima, IP (`audit_log`; asosiy amal bilan bitta tranzaksiyada). Parol jurnalga tushmaydi.
- `GET /security/audit` (`audit:read`, sahifalash va filtr), `GET /security/sessions` va `DELETE /security/sessions/{id}` (administrator), `GET /auth/sessions` va `DELETE /auth/sessions/{id}` (o'z sessiyalari). Sessiya bekor qilinganda refresh token bekor bo'ladi; amaldagi access token muddati tugaguncha (<=30 daqiqa) ishlashi mumkin.
- Mijoz IP'si: `X-Forwarded-For` faqat ishonchli proksidan (`TRUSTED_PROXIES`) hisobga olinadi, o'ngdan birinchi ishonchsiz manzil olinadi (soxtalashtirishga qarshi) (1-bosqich, band 7, backend qismi).

## [1.5.6] - 2026-11-03
### Security
- `SEED_DEMO` standarti `false` (`.env.example` va compose). `SEED_DEMO=false` bo'lsa va bazada foydalanuvchi bo'lmasa, `ADMIN_EMAIL` va `ADMIN_PASSWORD` (kamida 10 belgi) majburiy: aks holda backend ishga tushmaydi (konteyner xato bilan to'xtaydi). Bazada foydalanuvchilar bor bo'lsa, qayta ishga tushirishda parol talab qilinmaydi.

## [1.5.5] - 2026-11-03
### Removed
- `POST /auth/register`, Register sahifasi va Login'dagi "Ro'yxatdan o'ting" havolasi (API'ni buzadigan o'zgarish: ochiq ro'yxatdan o'tish yo'q).
### Added
- `POST /users`: xodim va loginni faqat administrator yaratadi (`roles:manage`).

## [1.5.4] - 2026-11-03
### Added
- pytest + httpx testlari (128 ta), alohida `<POSTGRES_DB>_test` bazasi (Alembic migratsiyalari bilan yaratiladi): auth va token oqimi, refresh aylantirish va oilani bekor qilish, RBAC matritsasi (5 rol x asosiy endpointlar), PINFL (422/409), restartdan keyin ma'lumot saqlanishi va seed idempotentligi, AI (mock), CSV, CORS.
- `docker compose --profile test run --rm test` (Dockerfile `test` bosqichi), `requirements-dev.txt`.
- ruff (`backend/pyproject.toml`); kod ruff'dan o'tdi (1-bosqich, band 10, backend qismi).
- `BCRYPT_ROUNDS` sozlamasi (testlarda kamaytiriladi).

## [1.5.3] - 2026-11-03
### Added
- Backend ruxsat tekshiruvi: har endpoint `require("<ruxsat>")` dependency'si orqali (403, token yo'q bo'lsa 401). Standart matritsa: EMR yozish faqat doctor/admin; moliya admin/cashier; xodimlar yozish va sozlamalar yozish faqat admin.
- `GET /permissions`, `GET/PUT /roles` (ruxsatlarni bazaga yozish; admin roli o'zgarmaydi), `GET/PATCH /users` (rol, faollashtirish; sessiyalar bekor qilinadi). Ruxsat: `roles:manage`.
- `cashier` roli (1-bosqich, band 6, backend qismi).

## [1.5.2] - 2026-11-03
### Changed
- Barcha routerlar PostgreSQL'ga o'tdi (xotiradagi `fake` ma'lumotlar olib tashlandi). `doctor` va `patient_name` matnlari saqlanmaydi: API javobida join orqali qaytariladi (frontend uchun javob shakli o'zgarmadi). ID lar UUID (1-bosqich, band 3).
- Refresh tokenlar bazada (`jti`, `revoked_at`): har refresh'da aylantiriladi; bekor qilingan token qayta ishlatilsa, foydalanuvchining barcha tokenlari bekor qilinadi.
- Bemorda `age` o'rniga `birth_date` saqlanadi (`age` hisoblanadi); `pinfl` (14 raqam, unikal) qo'llab-quvvatlanadi; qidiruv ism/telefon/PINFL bo'yicha.
- Uchrashuv, EMR, to'lov yozuvi bor bemorni/xodimni o'chirish 409 qaytaradi (faolsizlantirish tavsiya etiladi).
- `GET /finance/summary?period=week|month|year|all` bazadan hisoblanadi.
- `POST /auth/register` endi faol bo'lmagan hisob yaratadi (administrator faollashtiradi).
### Added
- `POST /auth/logout`, `POST /auth/change-password` (parol o'zgarganda barcha refresh tokenlar bekor qilinadi), `GET /auth/me`.
- Seed (`python -m app.seed`, idempotent): filial, rollar, ruxsatlar, sozlamalar har doim; demo ma'lumotlar faqat `SEED_DEMO=true` va bo'sh bazada; yoki `ADMIN_EMAIL`/`ADMIN_PASSWORD` bilan birinchi administrator (1-bosqich, band 4).
- Ruxsatlar katalogi va rollar: admin, doctor, nurse, receptionist, cashier (bazada; tekshiruv keyingi versiyada).

## [1.5.1] - 2026-11-03
### Added
- PostgreSQL 16 (compose: `db`, named volume `pgdata`, healthcheck, host portiga ochilmagan; credentials `.env` dan).
- SQLAlchemy 2 modellari va Alembic `0001_initial_schema`; konteyner ishga tushganda `alembic upgrade head`.
- Jadvallar: branches, users, staff, patients, appointments, encounters, prescriptions, transactions, clinic_settings, roles, permissions, role_permissions, audit_log, refresh_tokens.
- Native UUID PK (server tomonida `gen_random_uuid()`), `created_at/updated_at` (timestamptz), `created_by`, `branch_id`; Enum(native_enum=False)+CHECK; `patients.pinfl` 14 raqam, unikal; pul `numeric(14,2)`; encounters/prescriptions/transactions uchun `deleted_at`.
- `StaffRole.Cashier`.
### Note
- API hali xotiradagi ma'lumotlar bilan ishlaydi; routerlar bazaga keyingi versiyada o'tadi (1-bosqich, band 2–3).

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
