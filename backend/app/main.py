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
    click,
    commissions,
    emr,
    finance,
    icd10,
    invoices,
    lab,
    messaging,
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
## 🏥 Digital Clinic AI — Healthcare Management Platform API

Bu API raqamli klinika boshqaruv tizimi uchun mo'ljallangan.
Barcha endpointlar haqida to'liq ma'lumot ushbu sahifada mavjud.

### Asosiy bo'limlar:
- **🔐 Auth** — Foydalanuvchi autentifikatsiyasi (login, register, token)
- **👥 Patients** — Bemorlar boshqaruvi (CRUD)
- **📅 Appointments** — Uchrashuvlar rejalashtirish
- **📋 EMR** — Elektron tibbiy yozuvlar
- **💰 Finance** — Moliyaviy operatsiyalar
- **📊 Analytics** — Statistika va tahlil
- **🤖 AI Assistant** — AI yordamchi (tibbiy savollarga javob)
- **📝 Reports** — Hisobotlar generatsiyasi
- **👔 Staff** — Xodimlar boshqaruvi
- **⚙️ Settings** — Tizim sozlamalari

### Autentifikatsiya:
Ko'pgina endpointlar **Bearer Token** talab qiladi.
Login qilingandan so'ng olingan tokenni `Authorization: Bearer <token>` headerida yuboring.
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


for module in (access, auth, security, patients, appointments, emr, finance, analytics, ai, staff, settings_router,
               reports, rooms, schedule, waitlist, icd10, lab, attachments, services, invoices, payments, payme, click,
               commissions, shifts, messaging, public, public_booking, portal, warehouse):
    app.include_router(module.router)
