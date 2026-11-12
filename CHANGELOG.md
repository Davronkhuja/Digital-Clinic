# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versiyalash: [SemVer](https://semver.org/).

## [1.7.2] - 2026-11-12
### Added
- Moliya (3/6): to'lovlar va qaytarishlar (`payments`, `payment_refunds`, migratsiya 0019). `POST /invoices/{id}/payments` (naqd/karta, `finance:write`): hisob-faktura `Issued`/`PartiallyPaid` bo'lishi, summa qoldiqdan oshmasligi (qisman to'lov mumkin); hisob-faktura holati to'lovlardan `PartiallyPaid`/`Paid` ga hisoblanadi, `paid_amount`/`refunded_amount`/`balance` javobda.
- Har to'lov fiskal chek bilan yopiladi: `services/fiscal.py` adapter interfeysi (`sale`/`refund`) va `MockFiscalAdapter` (chek ID `MOCK-...`, fiscal_sign, tashqi so'rov yo'q); `FISCAL_BACKEND=mock` (real operator uchun hujjat va kalit kerak). Chek qatorlari: nom, MXIK, package_code, soni, summa va QQS (tiyinda, `money.to_tiyin`); qisman to'lovda qatorlarga proporsional, yig'indi aynan to'lovga teng. Kassada chek berilmasa to'lov yozilmaydi (502); `POST /payments/{id}/receipt` chekni qayta beradi (provayder to'lovlari uchun).
- Daromad avtomatik: to'lov `transactions` ga `income` ("Xizmat to'lovi"), qaytarish `expense` ("Qaytarish") bo'lib yoziladi (`transactions.payment_id/refund_id`), shuning uchun mavjud moliya va tahlil raqamlari ularni ko'radi.
- `POST /payments/{id}/refunds` (`finance:refund`, faqat admin; sabab majburiy): to'liq yoki qisman, jami to'langanidan oshmaydi, qaytarish fiskal cheki, xarajat yozuvi, hisob-faktura holati qayta hisoblanadi, auditga `refund`. Click/Payme to'lovi provayder orqali qaytariladi (v1.7.3-1.7.4).
- To'lovi bor hisob-fakturani bekor qilib bo'lmaydi (qaytarish orqali). `GET /invoices/{id}/payments`. Hammasi auditda.

## [1.7.1] - 2026-11-12
### Added
- Moliya (2/6): hisob-fakturalar. `invoices` + `invoice_lines` (migratsiya 0018), raqam `INV-000123` (DB ketma-ketligi). Qatorda xizmat nomi, MXIK, package_code, QQS foizi va narx nusxalanadi: narxnoma keyin o'zgarsa ham hisob-faktura o'zgarmaydi. Faqat sotiladigan xizmat (MXIK, package_code, QQS to'liq, faol), aks holda 422 (qaysi maydon yetishmasligi ko'rsatiladi).
- Hisob: pul faqat Decimal, numeric(14,2); qator chegirmasi (foiz yoki summa), hisob-faktura chegirmasi qatorlarga proporsional taqsimlanadi (yaxlitlash qoldig'i aniq taqsimlanadi, yig'indi har doim `total`), QQS narx ichidan: `net * p / (100 + p)`. DB CHECK: `total = subtotal - discount_total`, qator `net_total` ham.
- `POST /invoices` (`finance:write`; `issue=true` darhol chiqaradi), `GET /invoices[?patient_id&status&number]`, `GET /invoices/{id}`, `PUT /invoices/{id}` (faqat `Draft`), `POST /invoices/{id}/issue`, `POST /invoices/{id}/cancel` (sabab majburiy; to'lovi borini emas). Hisob-faktura o'chirilmaydi. Qabul/ko'rik bemorga tegishli bo'lishi shart; bitta qabulga faol hisob-faktura bitta (409). Ijrochi shifokor qatorda (standart: qabul shifokori) shifokor foizi uchun.
- Chegirma `finance:discount` ruxsati (admin, kassir) va sabab bilan; foiz va summa birga berilmaydi; hammasi auditga (summa, chegirma).
- `services/money.py`: pulni yaxlitlash va so'm <-> tiyin o'tkazish bitta joyda (Payme/Click adapterlari shundan foydalanadi).
- **Taxmin**: `finance:discount` kassirga ham berildi (qoida aniq emas; Sozlamalar > Rollar orqali o'zgartiriladi). Qoldiq/to'langan summa v1.7.2 da to'lovlar bilan.

## [1.7.0] - 2026-11-12
### Added
- 3-bosqich, moliya (1/6): narxnoma. `services` (migratsiya 0017) va `service_categories`. Har xizmatda `price` (numeric(14,2), QQS bilan), `mxik` (IKPU, aniq 17 raqam; bo'sh joy va chiziqcha tozalanadi), `package_code` (1-10 raqam), `vat_percent` (0-100; 0 = QQSsiz, null = kiritilmagan). Format DB CHECK va API (422) da tekshiriladi.
- Bularsiz xizmatni sotib bo'lmaydi: MXIK, package_code yoki QQS bo'lmasa xizmat saqlanadi, lekin `sellable=false` (`missing` ro'yxati bilan); faol bo'lmagan xizmat ham sotilmaydi. `GET /services?sellable=true|false&search&category_id&include_inactive`. Hisob-faktura (v1.7.1) faqat `sellable` xizmatni qabul qiladi.
- `GET/POST/PUT /services`, `GET/POST/PUT /service-categories`; yangi ruxsatlar `services:read` (admin, shifokor, qabulxona, katta registrator, kassir) va `services:write` (faqat admin); xizmat o'zgarishlari (narx va h.k.) auditga eski/yangi qiymat bilan. Xizmat o'chirilmaydi, faolsizlantiriladi.
- Frontend: Sozlamalar > "Narxnoma" (ro'yxat, filtr: sotiladigan / kodi to'liq emas, qo'shish/tahrirlash, MXIK jonli tekshiruvi).
- **Taxmin**: `package_code` formati (1-10 raqam) va MXIK uchun faqat uzunlik/raqam tekshiruvi (rasmiy klassifikator bilan solishtirish yo'q); QQS stavkasi qat'iy kodlanmagan (soliq stavkasi o'zgarishi mumkin).

## [1.6.18] - 2026-11-12
### Added
- Majburan yozish: `appointments:override` ruxsati (admin va yangi "Katta registrator" roli `senior_receptionist`; migratsiya 0016 mavjud bazaga ruxsat va rolni qo'shadi, bo'sh bazada seed). Ish vaqtidan tashqari (soat, tanaffus, dam olish kuni, ta'til, qo'shimcha slot) yozishda `override_reason` majburiy (kamida 5 belgi): sabab yo'q 422, sabab bor lekin ruxsat yo'q 403.
- Shifokor va kabinet to'qnashuvi override bilan ham taqiqlangan (409, bazadagi cheklov).
- Har override auditga alohida `override` hodisasi bilan (sabab, buzilish matni, shifokor, bemor, vaqt, kim); qabulda `override_reason`/`override_by` saqlanadi. Ish vaqtiga qaytarilsa iz tozalanadi.
- Yozish (`POST /appointments`), ko'chirish (`PATCH`) va kutish ro'yxatidan yozish (`POST /waitlist/{id}/book`) bir xil qoida bilan (`services/booking.py`: `apply_working_rule`, `save_booking`).
- Frontend: ruxsati borlarga qabul formasida "Majburan yozish sababi", ro'yxatda "majburan" belgisi.

## [1.6.17] - 2026-11-12
### Added
- Ma'lumotnomalarda `verified` (bool) va `source`: MKB-10, INN, lab tahlil va lab me'yor (migratsiya 0015). Starter yozuvlar `verified=false`, `source="starter (namuna)"` (mavjud bazadagilar ham). API javoblarida (`/icd10`, `/inn`, `/lab/tests`) ko'rinadi.
- Import skriptlari (`import_mkb10.py`, `import_inn.py`) importdan keyin `verified=true` va `source` (`--source`, standart fayl nomi) qo'yadi; fayl nomida "starter" bo'lsa namuna (false) qoladi.
- `POST /icd10/verify`, `POST /inn/verify` (`settings:write`): `items` yoki `all=true` va `source` bilan tasdiqlash, auditga yoziladi.
- Lab me'yorlarini administrator tahrirlaydi (`PUT /lab/tests/{id}`, `ranges` har biri `verified`/`source` bilan; qo'lda kiritilgan me'yor tasdiqlangan, manba berilmasa "klinika (qo'lda kiritilgan)"). Natijaga solishtirilgan me'yorning tasdig'i nusxalanadi (`ref_verified`): eski natijalar o'zgarmaydi. PDF namuna me'yor ishlatilgan bo'lsa ogohlantiradi.
- Frontend: MKB-10, INN, ko'rik kartasi va laboratoriya natijalarida "namuna" belgisi; Sozlamalar > "Laboratoriya me'yorlari" (jins/yosh/chegara/manba tahriri, saqlangach tasdiqlangan).

## [1.6.16] - 2026-11-12
### Added
- EMR fayl ilovalari: `POST /patients/{id}/attachments` (multipart, ixtiyoriy `encounter_id` va `note`; `emr:write`), `GET /patients/{id}/attachments[?encounter_id]`, `GET /attachments/{id}/download` (`emr:read`, `attachment` + `nosniff` + `no-store`), `DELETE /attachments/{id}` (yozuv `deleted_at`, fayl saqlashda qoladi). Hammasi auditga yoziladi (yuklash, ro'yxat, yuklab olish, olib tashlash).
- Tur baytlar bo'yicha aniqlanadi (PDF, JPG, PNG, DICOM `DICM`): kengaytma va Content-Type'ga ishonilmaydi, noma'lum tur 415, bo'sh fayl 422, hajm `MAX_UPLOAD_MB` (standart 20) dan oshsa 413. Fayl nomi tozalanadi (yo'l ajratgichlar olib tashlanadi), kengaytma haqiqiy turga moslanadi. Saqlash kaliti server yaratgan UUID.
- Saqlash interfeysi `services/storage.py` (`Storage`: save/open/exists); hozir `LocalStorage` (docker volume `uploads` -> `/data/uploads`, atomik yozish, yo'l chiqib ketmaydi), `STORAGE_BACKEND` bilan keyin S3/MinIO. Migratsiya 0014. nginx `client_max_body_size 25m`.
- Frontend: `AttachmentsPanel` (ko'rik formasida va bemor profilida: yuklash, yuklab olish, olib tashlash).
### Changed
- Eski EMR formasidagi simptom chiplari saqlanganda "Shikoyatlar" bo'limiga matn sifatida qo'shiladi ("Simptomlar: ..."); saqlanmaydigan eski "Lab Results" va "Attachments" bloklari olib tashlandi.

## [1.6.15] - 2026-11-12
### Added
- 2-bosqich "Shart"i e2e test bilan isbotlandi (`tests/test_e2e_stage2.py`): bemor qo'shish (kirill/lotin, telefon qidiruvi), bo'sh vaqt (jadval, tanaffus), yozish (davomiylik, kabinet, band vaqt 409), ko'rik (shablon, MKB-10, qabul `Completed`), laboratoriya (to'plam, hamshira natijasi, me'yor belgisi), INN retsept, DMED tartibidagi karta, PDF, "ko'chirildi" belgisi va butun zanjir auditi.
### Changed
- `CLAUDE.md`: 2-bosqich tugadi, yangi qarorlar (vaqt, band vaqt, katalog, ruxsatlar) va ochiq masalalar.

## [1.6.14] - 2026-11-12
### Added
- EMR (4/4): ko'rik kartasi DMED maydonlari tartibida. `GET /emr/{id}/card`: bemor (F.I.Sh., tug'ilgan sana, jins, PINFL, telefon, manzil), murojaat (sana, shifokor), ko'rik (shikoyat, anamnez, ob'ektiv ko'rik, tashxis + MKB-10 kodi va nomi, tavsiya), retsept (INN, doza, usul, chastota, muddat, bir qatorli matn), ko'rikka bog'langan laboratoriya natijalari. `GET /emr/{id}/card/pdf`: chop etish uchun PDF.
- "DMED ga ko'chirildi" belgisi qo'lda (API yo'q): `POST /emr/{id}/dmed-mark {copied}` (`emr:write`), kim va qachon (`encounters.dmed_copied_at/by`, migratsiya 0013), auditga yoziladi; `EMRRecord.dmed_copied_at`.
- `POST /lab/orders`: `encounter_id` ko'rik shu bemorniki bo'lishi shart (422).
- Frontend: EMR ro'yxatida "DMED ko'rik kartasi" (har maydon, MKB-10 kodi, INN, doza alohida nusxalanadi, "Hammasini nusxalash", "ko'chirildi" belgisi, chop etish PDF); ro'yxatda "DMED ✓" belgisi.
- **Taxmin**: DMED ning aniq maydon tartibi hujjati yo'q edi; tartib yuqoridagi umumiy ko'rik tuzilmasi bo'yicha qo'yildi, haqiqiy DMED shakli bilan solishtirib tuzatish kerak (ochiq masala).

## [1.6.13] - 2026-11-12
### Added
- Laboratoriya (2/2): `GET /lab/orders/{id}/pdf` (`lab:read`): klinika sarlavhasi, bemor (ism, tug'ilgan sana, jins), shifokor, jadval (tahlil, natija, birlik, me'yor, belgi); me'yordan tashqari qiymat qalin va qizil; natijasiz tahlil "—". Kirill va lotin DejaVu shrifti bilan (Dockerfile: `fonts-dejavu-core`; topilmasa Helvetica). PDF ochilishi auditga yoziladi. Kutubxona: reportlab 4.2.2 (testlarda pypdf bilan matn tekshiriladi).
- Frontend: "Laboratoriya" sahifasi (menyu, `lab:read`): buyurtmalar ro'yxati (holat, me'yordan tashqari soni), yangi buyurtma (to'plam va alohida tahlillar), natija kiritish va me'yor bilan belgi, buyurtmani bekor qilish, PDF.

## [1.6.12] - 2026-11-12
### Added
- Laboratoriya (1/2, backend): katalog `lab_tests` + jins/yosh bo'yicha me'yorlar `lab_reference_ranges` (faqat past yoki faqat yuqori chegara mumkin), to'plamlar (natija shablonlari) `lab_panels`, buyurtmalar `lab_orders` + `lab_order_items` (migratsiya 0012). Yangi ruxsatlar `lab:read`, `lab:write` (admin, shifokor, hamshira; migratsiya mavjud rollarga beradi).
- `GET/POST/PUT /lab/tests`, `GET/POST/PUT /lab/panels` (o'qish `lab:read`, yozish `settings:write`; tahlil o'chirilmaydi, faolsizlantiriladi).
- `POST /lab/orders` (to'plam va/yoki alohida tahlillar, takrorlar bir marta), `GET /lab/orders[?patient_id&status]`, `GET /lab/orders/{id}`, `PUT /lab/orders/{id}/results`, `POST /lab/orders/{id}/cancel`. Buyurtma o'chirilmaydi (bekor qilinadi); o'qish va yozish auditda.
- Natija bemorning jinsi va yoshiga mos me'yor bilan solishtiriladi: `Low`/`Normal`/`High`; chegarada qiymat me'yor. Mos me'yor bo'lmasa (masalan, bola uchun kattalar me'yori, yosh noma'lum) `flag` null: noto'g'ri me'yor bilan solishtirilmaydi. Nom, birlik va me'yor natijaga nusxalanadi: katalog keyin o'zgarsa ham yozilgan natija o'zgarmaydi. Natijani tuzatish mumkin, hamma tahlil natijali bo'lsa buyurtma `Completed`.
- Starter katalog (`data/lab_starter.json`): 24 ta oddiy ko'rsatkich (UQT, biokimyo, lipid profili, SRO, TTG, HbA1c, ferritin), 3 to'plam, kattalar (18+) me'yorlari. **Rasmiy me'yor emas**: klinika va laboratoriya tasdiqlashi, kerak bo'lsa tahrirlashi shart (ochiq masala).
- PDF va frontend keyingi versiyada (v1.6.13).

## [1.6.11] - 2026-11-12
### Added
- EMR (3/4): INN bo'yicha tuzilgan retsept. `POST/GET /emr/{id}/prescriptions` (`inn`, `dose`, `route`, `frequency`, `duration_days` 1-365, `instructions`); INN ma'lumotnomada bo'lishi shart (422), kanonik nomga keltiriladi; yuborish usullari: Oral, Intravenous, Intramuscular, Subcutaneous, Topical, Inhalation, Sublingual, Rectal, Ophthalmic, Nasal, Otic, Vaginal. Yig'ma matn `medication` ("amlodipine 5 mg, ichga, kuniga 1 marta, 30 kun") ro'yxat va DMED ga ko'chirish uchun. `EMRRecord.prescriptions` ro'yxati.
- `DELETE /prescriptions/{id}`: retsept o'chirilmaydi, `deleted_at` bilan bekor qilinadi (audit `create`/`delete`).
- INN ma'lumotnomasi (`inn_drugs`, migratsiya 0011): `GET /inn?search=` (nom/so'z boshi/guruh), `POST /inn` (`settings:write`), import skripti `scripts/import_inn.py <fayl.csv>` (`inn[,group_uz]`, idempotent). Bo'sh ma'lumotnomaga `data/inn_starter.csv` (146 ta) yuklanadi. **Starter rasmiy ro'yxat emas**: guruh nomlari muallif tomonidan yozilgan, shifokor tekshirishi shart (ochiq masala).
- Frontend: EMR formasida retsept muharriri (INN avtoto'ldirish, doza, usul, chastota, muddat), saqlangan retseptlarni bekor qilish. Eski saqlanmaydigan "Medications" jadvali olib tashlandi.

## [1.6.10] - 2026-11-12
### Added
- EMR (2/4): ko'rik bo'limlari `complaints`, `anamnesis`, `examination`, `recommendations` (tashxis va MKB-10 avvaldan) DMED ko'rik kartasi tartibida; `POST /emr` va `EMRRecord` da.
- `PUT /emr/{id}`: ko'rikni tahrirlash (o'chirilmaydi; audit `update`, o'zgargan maydonlar nomi bilan). Frontend tahrirlashda endi yangi yozuv yaratmaydi, mavjudini yangilaydi.
- `POST /emr` da `appointment_id`: qabul shu bemorniki bo'lishi shart (422), bekor/kelmagan bo'lsa 409; saqlanganda qabul `Completed` bo'ladi (qog'ozsiz zanjir: qabul -> ko'rik).
- Ko'rik shablonlari (`exam_templates`, migratsiya 0010): `GET/POST/PUT/DELETE /emr-templates` (o'qish `emr:read`, yozish `emr:write`; nomi registrsiz unikal). Seed: 2 ta bo'sh andoza (faqat sarlavhalar, klinik matn yo'q).
- Frontend: EMR formasida bo'limlar, shablon tanlash (faqat bo'sh bo'limlar to'ldiriladi), qabulga bog'lash; Sozlamalar > "Ko'rik shablonlari".

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
