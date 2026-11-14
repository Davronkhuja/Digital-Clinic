"""
Digital Clinic AI - FastAPI Backend
====================================
API hujjatlari: /docs (Swagger UI) yoki /redoc
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.core.config import settings
from app.routers import (
    access,
    ai,
    analytics,
    appointments,
    attachments,
    auth,
    branches,
    click,
    commissions,
    emr,
    exports,
    finance,
    icd10,
    insurance,
    invoices,
    lab,
    messaging,
    notifications,
    patients,
    payme,
    payments,
    portal,
    public,
    public_booking,
    reports,
    rooms,
    schedule,
    security,
    services,
    shifts,
    staff,
    waitlist,
    warehouse,
)
from app.routers import settings as settings_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Digital Clinic AI",
    description="""
## Digital Clinic: ochiq REST API

Xususiy klinikalar boshqaruv tizimi (bemorlar, qabullar, EMR, laboratoriya, moliya, ombor, sug'urta, hisobotlar).
Tashqi tizimlar (buxgalteriya, call-markaz, mobil ilova) shu API orqali ulanadi. To'liq qo'llanma: `docs/API.md`.

### Autentifikatsiya
`POST /auth/login` -> `access_token` (30 daqiqa) va `refresh_token` (7 kun, har safar aylantiriladi: `POST /auth/refresh`).
Keyingi so'rovlarda `Authorization: Bearer <access_token>`. Ro'yxatdan o'tish yo'q: xodim va loginni administrator yaratadi (`POST /users`).
Bemor portali alohida: telefon + OTP (`/portal/*`), xodim tokeni bilan aralashmaydi.

### Ruxsatlar
Har endpoint ruxsat talab qiladi (masalan `patients:read`, `finance:write`); rol ruxsatlari Sozlamalarda. Ruxsat yo'q: **403**.
Token yo'q yoki yaroqsiz: **401**.

### Filial
Foydalanuvchi o'z filialida ishlaydi. `branches:all` ruxsati bor foydalanuvchi `X-Branch-Id: <filial id>` sarlavhasi bilan
boshqa filialni tanlaydi.

### Xatolar
`{"detail": "..."}`. **404** topilmadi, **409** ziddiyat (band vaqt, yetmagan qoldiq, tasdiqlangan natijani o'zgartirish),
**422** tekshiruv xatosi, **429** tezlik cheklovi (OTP).

### Qiymatlar
ID lar satr (UUID). Vaqt ISO 8601 (UTC, klinika vaqti Asia/Tashkent). Pul `numeric(14,2)`, valyuta so'm; miqdor 3 xonagacha.
Bemor va moliya ma'lumotlarini o'qish/yozish auditga yoziladi.

### Hisobotlar va eksport
`/reports/analytics/{kind}` (JSON, `format=xlsx|pdf`), `/exports/{dataset}` (1C uchun universal eksport: Excel/CSV),
`/insurance/registry` (sug'urta reyestri, Excel).
Payme (`/payme`) va Click (`/click`) ochiq endpointlari provayderning o'z imzosi bilan himoyalangan.
    """,
    version=__version__,
    contact={
        "name": "Digital Clinic Support",
        "email": "support@digitalclinic.uz",
    },
    license_info={
        "name": "MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/", tags=["Root"], summary="API sog'ligi tekshiruvi")
def root():
    """API ishlayotganini tekshirish uchun endpoint."""
    return {"status": "ok", "message": "Digital Clinic AI API", "docs": "/docs"}


for module in (access, auth, branches, security, patients, appointments, emr, finance, analytics, ai, staff, settings_router,
               reports, rooms, schedule, waitlist, icd10, lab, attachments, services, invoices, payments, payme, click,
               commissions, shifts, exports, insurance, messaging, notifications, public, public_booking, portal, warehouse):
    app.include_router(module.router)
