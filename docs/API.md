# Digital Clinic: ochiq REST API qo'llanmasi

Interaktiv hujjat: `http://localhost:8010/docs` (Swagger), `/redoc`, sxema: `/openapi.json`.
Barcha endpoint va maydonlar shu yerda; bu fayl umumiy qoidalarni beradi.

## Autentifikatsiya

```bash
curl -s -X POST localhost:8010/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@clinic.uz","password":"..."}'          # -> access_token, refresh_token
curl -s localhost:8010/patients -H "Authorization: Bearer $ACCESS"
curl -s -X POST localhost:8010/auth/refresh -d '{"refresh_token":"..."}' -H 'Content-Type: application/json'
```

- Access token 30 daqiqa. Refresh 7 kun, har yangilashda aylantiriladi; ishlatilgan eski refresh qayta kelsa butun oila bekor qilinadi.
- Ro'yxatdan o'tish va parolni tiklash yo'q: xodim/loginni administrator yaratadi (`POST /users`).
- Tashqi tizim uchun alohida xizmat foydalanuvchisi yarating va unga faqat kerakli rolni bering.
- Bemor portali (`/portal/*`): telefon + OTP, alohida seans; xodim tokeni bilan aralashmaydi.

## Ruxsatlar va filial

- Har endpoint ruxsat talab qiladi (`patients:read`, `finance:write`, `exports:read`, ...). 401 token yo'q, 403 ruxsat yo'q.
- Foydalanuvchi o'z filialida ishlaydi. `branches:all` bo'lsa `X-Branch-Id: <id>` bilan boshqa filialni tanlaydi; hisobot va eksportda `all_branches=true`.

## Umumiy qoidalar

| Mavzu | Qoida |
|---|---|
| ID | UUID satr |
| Vaqt | ISO 8601; qabul `starts_at/ends_at` UTC, klinika vaqti Asia/Tashkent |
| Pul | so'm, 2 xona (`numeric(14,2)`); ombor miqdori 3 xona |
| Xato | `{"detail": "..."}`: 404 topilmadi, 409 ziddiyat, 422 tekshiruv, 429 tezlik cheklovi |
| Ro'yxat | `skip`/`limit` (ko'p endpointda `limit` <= 100) |
| O'chirish | EMR, retsept, to'lov o'chirilmaydi (`deleted_at`); yozuvli bemor/xodim faolsizlantiriladi (409) |
| Audit | bemor, EMR, to'lov, hisobot/eksport yuklash va kirish hodisalari `audit_log` ga yoziladi |

## Asosiy oqimlar

- **Bemor va qabul:** `POST /patients`, `GET /appointments/availability`-turdagi bo'sh vaqtlar (Swagger: Schedule), `POST /appointments` (band vaqt: 409).
- **Hisob-faktura va to'lov:** `/invoices`, `/payments` (Cash/Card kassada, ochiq smena shart; Payme/Click `Pending` -> provayder chaqiruvi); fiskal chek bilan yopiladi.
- **Sug'urta (DMS):** `/insurance/*`: kompaniya -> shartnoma -> polis -> kafolat xati; hisob-faktura bemor va sug'urta ulushiga bo'linadi; `/insurance/debts`, `/insurance/registry`.
- **Hisobotlar:** `GET /reports/analytics/{kind}` (`revenue`, `patient_flow`, `doctor_load`, `no_show`), `format=json|xlsx|pdf`.
- **Buxgalteriya / 1C:** `GET /exports/{dataset}` (`sales`, `payments`, `cash_shifts`, `stock_movements`, `commissions`), `format=xlsx|csv`, `date_from`, `date_to`. Ustun xaritasi: `/settings/exports`.
- **AI xulosa:** `/emr/{id}/ai-summary` (qoralama), `.../approve`, `.../reject`; `AI_ENABLED=false` bo'lsa demo matn (tasdiqlanmaydi).

## Provayder webhooklari

`/payme` (JSON-RPC, Basic auth) va `/click/*` (imzo) ochiq, lekin kalitsiz hamma so'rovni rad etadi. Kalitlar faqat `.env` da.

## Versiya

API versiyasi `GET /openapi.json` -> `info.version` (SemVer, `VERSION` bilan bir). API'ni buzadigan o'zgarish MAJOR.
