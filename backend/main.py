"""
Digital Clinic AI - FastAPI Backend
====================================
API Documentation available at: /docs (Swagger UI) or /redoc (ReDoc)
"""

from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime, date
from enum import Enum
import random
import csv
import io
import os
import logging

import httpx
import bcrypt
import jwt
from datetime import timedelta, timezone

__version__ = "1.4.2"
logger = logging.getLogger("digital_clinic")

# ─────────────────────────────────────────────
#  App initialization
# ─────────────────────────────────────────────

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

# Vergul bilan ajratilgan aniq originlar; "*" ruxsat etilmaydi (credentials bilan xavfli)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5180").split(",") if o.strip()]
if "*" in CORS_ORIGINS:
    raise RuntimeError("CORS_ORIGINS ichida '*' ishlatib bo'lmaydi; aniq originlarni ko'rsating.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

security = HTTPBearer(auto_error=False)

# ─────────────────────────────────────────────
#  Enums
# ─────────────────────────────────────────────

class GenderEnum(str, Enum):
    male = "male"
    female = "female"
    other = "other"

class StatusEnum(str, Enum):
    active = "Active"
    inactive = "Inactive"

class AppointmentStatus(str, Enum):
    scheduled = "Scheduled"
    completed = "Completed"
    cancelled = "Cancelled"
    no_show = "No Show"

class TransactionType(str, Enum):
    income = "income"
    expense = "expense"

class StaffRole(str, Enum):
    doctor = "Doctor"
    nurse = "Nurse"
    receptionist = "Receptionist"
    admin = "Admin"
    lab_tech = "Lab Technician"

# ─────────────────────────────────────────────
#  Pydantic Models
# ─────────────────────────────────────────────

# Auth
class LoginRequest(BaseModel):
    email: EmailStr = Field(..., example="admin@clinic.uz")
    password: str = Field(..., min_length=6, example="password123")

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, example="Ahmad Karimov")
    email: EmailStr = Field(..., example="ahmad@clinic.uz")
    password: str = Field(..., min_length=6, example="securepass123")
    clinic_name: str = Field(..., example="Hayot Klinnikasi")

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RefreshRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(..., example="admin@clinic.uz")

# Patient
class PatientCreate(BaseModel):
    name: str = Field(..., example="Aziza Karimova")
    phone: str = Field(..., example="+998 90 123 4567")
    age: int = Field(..., ge=0, le=150, example=34)
    gender: GenderEnum = Field(..., example="female")
    doctor: Optional[str] = Field(None, example="Dr. Rustamov")
    address: Optional[str] = Field(None, example="Toshkent, Yunusobod")
    blood_type: Optional[str] = Field(None, example="A+")
    allergies: Optional[str] = Field(None, example="Penisilin")

class PatientUpdate(PatientCreate):
    name: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[GenderEnum] = None

class Patient(PatientCreate):
    id: str
    status: StatusEnum = StatusEnum.active
    last_visit: Optional[str] = None
    created_at: str

# Appointment
class AppointmentCreate(BaseModel):
    patient_id: str = Field(..., example="1")
    patient_name: str = Field(..., example="Aziza Karimova")
    doctor: str = Field(..., example="Dr. Rustamov")
    date: str = Field(..., example="2026-02-25")
    time: str = Field(..., example="10:00")
    type: str = Field(..., example="Konsultatsiya")
    notes: Optional[str] = Field(None, example="Qon bosimi tekshiruvi")

class Appointment(AppointmentCreate):
    id: str
    status: AppointmentStatus = AppointmentStatus.scheduled
    created_at: str

# EMR
class EMRCreate(BaseModel):
    patient_id: str = Field(..., example="1")
    patient_name: str = Field(..., example="Aziza Karimova")
    doctor: str = Field(..., example="Dr. Rustamov")
    diagnosis: str = Field(..., example="Gipertenziya 2-darajali")
    prescription: str = Field(..., example="Amlodipine 5mg kuniga 1 marta")
    notes: Optional[str] = Field(None, example="Qon bosimi nazorat ostida")
    visit_date: str = Field(..., example="2026-02-23")

class EMRRecord(EMRCreate):
    id: str
    created_at: str

# Finance
class TransactionCreate(BaseModel):
    type: TransactionType = Field(..., example="income")
    amount: float = Field(..., gt=0, example=250000)
    description: str = Field(..., example="Konsultatsiya to'lovi")
    patient_name: Optional[str] = Field(None, example="Aziza Karimova")
    category: str = Field(..., example="Consultation")
    date: str = Field(..., example="2026-02-23")

class Transaction(TransactionCreate):
    id: str
    created_at: str

# Staff
class StaffCreate(BaseModel):
    name: str = Field(..., example="Dr. Behruz Rustamov")
    role: StaffRole = Field(..., example="Doctor")
    department: str = Field(..., example="Kardiologiya")
    phone: str = Field(..., example="+998 90 111 2233")
    email: EmailStr = Field(..., example="rustamov@clinic.uz")
    schedule: Optional[str] = Field(None, example="Dushanba-Juma, 09:00-17:00")

class StaffMember(StaffCreate):
    id: str
    status: StatusEnum = StatusEnum.active
    joined_date: str
    patients_count: int = 0

# AI
class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=4000)

class AIMessage(BaseModel):
    message: str = Field(..., max_length=4000, example="Bemorning qon bosimi ko'tarilgan. Nima qilish kerak?")
    context: Optional[str] = Field(None, max_length=2000, example="Bemor 54 yoshli, qandli diabet bilan")
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)

class AnalyzeRequest(BaseModel):
    period: str = Field("month", pattern="^(week|month|year)$")
    stats: str = Field(..., max_length=6000, description="Klinika statistikasi (matn)")

class AnalyzeResponse(BaseModel):
    analysis: str
    demo: bool = False
    disclaimer: str

class AIResponse(BaseModel):
    response: str
    demo: bool = False
    suggestions: List[str]
    disclaimer: str

# Settings
class ClinicSettings(BaseModel):
    clinic_name: str = Field(..., example="Digital Klinika")
    address: str = Field(..., example="Toshkent, Amir Temur ko'chasi 1")
    phone: str = Field(..., example="+998 71 200 0000")
    email: EmailStr = Field(..., example="info@clinic.uz")
    currency: str = Field(default="UZS", example="UZS")
    timezone: str = Field(default="Asia/Tashkent", example="Asia/Tashkent")
    language: str = Field(default="uz", example="uz")

# ─────────────────────────────────────────────
#  Password hashing (bcrypt)
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    # bcrypt faqat birinchi 72 baytni hisobga oladi
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], password_hash.encode())
    except ValueError:
        return False

# ─────────────────────────────────────────────
#  Fake Database
# ─────────────────────────────────────────────

fake_users = {
    "admin@clinic.uz": {"id": "1", "name": "Admin User", "email": "admin@clinic.uz",
                         "password_hash": hash_password("password123"), "role": "admin"}
}

fake_patients = [
    Patient(id="1", name="Aziza Karimova", phone="+998 90 123 4567", age=34, gender=GenderEnum.female,
            last_visit="2026-02-20", status=StatusEnum.active, doctor="Dr. Rustamov",
            blood_type="A+", address="Toshkent, Yunusobod", created_at="2025-01-10"),
    Patient(id="2", name="Bobur Aliyev", phone="+998 91 234 5678", age=45, gender=GenderEnum.male,
            last_visit="2026-02-18", status=StatusEnum.active, doctor="Dr. Karimov",
            blood_type="O+", address="Toshkent, Chilonzor", created_at="2025-02-15"),
    Patient(id="3", name="Dilnoza Rahimova", phone="+998 93 345 6789", age=28, gender=GenderEnum.female,
            last_visit="2026-02-15", status=StatusEnum.inactive, doctor="Dr. Yusupov",
            blood_type="B-", address="Samarqand", created_at="2025-03-20"),
    Patient(id="4", name="Eldor Toshmatov", phone="+998 94 456 7890", age=52, gender=GenderEnum.male,
            last_visit="2026-02-22", status=StatusEnum.active, doctor="Dr. Rustamov",
            blood_type="AB+", address="Toshkent, Mirzo Ulugbek", created_at="2025-04-05"),
    Patient(id="5", name="Feruza Umarova", phone="+998 95 567 8901", age=39, gender=GenderEnum.female,
            last_visit="2026-02-21", status=StatusEnum.active, doctor="Dr. Karimov",
            blood_type="A-", address="Andijon", created_at="2025-05-12"),
]

fake_appointments = [
    Appointment(id="1", patient_id="1", patient_name="Aziza Karimova", doctor="Dr. Rustamov",
                date="2026-02-25", time="10:00", type="Konsultatsiya",
                status=AppointmentStatus.scheduled, created_at="2026-02-22"),
    Appointment(id="2", patient_id="2", patient_name="Bobur Aliyev", doctor="Dr. Karimov",
                date="2026-02-25", time="11:30", type="Tekshiruv",
                status=AppointmentStatus.scheduled, created_at="2026-02-22"),
    Appointment(id="3", patient_id="3", patient_name="Dilnoza Rahimova", doctor="Dr. Yusupov",
                date="2026-02-24", time="09:00", type="Jarrohlik",
                status=AppointmentStatus.completed, created_at="2026-02-20"),
]

fake_emr = [
    EMRRecord(id="1", patient_id="1", patient_name="Aziza Karimova", doctor="Dr. Rustamov",
              diagnosis="Gipertenziya 2-darajali", prescription="Amlodipine 5mg",
              visit_date="2026-02-20", created_at="2026-02-20"),
    EMRRecord(id="2", patient_id="2", patient_name="Bobur Aliyev", doctor="Dr. Karimov",
              diagnosis="Qandli diabet 2-turi", prescription="Metformin 500mg",
              visit_date="2026-02-18", created_at="2026-02-18"),
]

fake_transactions = [
    Transaction(id="1", type=TransactionType.income, amount=250000,
                description="Konsultatsiya to'lovi", patient_name="Aziza Karimova",
                category="Consultation", date="2026-02-23", created_at="2026-02-23"),
    Transaction(id="2", type=TransactionType.income, amount=450000,
                description="Jarrohlik xizmati", patient_name="Bobur Aliyev",
                category="Surgery", date="2026-02-22", created_at="2026-02-22"),
    Transaction(id="3", type=TransactionType.expense, amount=1200000,
                description="Tibbiy jihozlar", patient_name=None,
                category="Equipment", date="2026-02-21", created_at="2026-02-21"),
    Transaction(id="4", type=TransactionType.income, amount=180000,
                description="Laboratoriya tahlili", patient_name="Dilnoza Rahimova",
                category="Lab", date="2026-02-20", created_at="2026-02-20"),
]

fake_staff = [
    StaffMember(id="1", name="Dr. Behruz Rustamov", role=StaffRole.doctor, department="Kardiologiya",
                phone="+998 90 111 2233", email="rustamov@clinic.uz", status=StatusEnum.active,
                joined_date="2023-01-15", patients_count=124, schedule="Du-Ju 09:00-17:00"),
    StaffMember(id="2", name="Dr. Zulfiya Karimova", role=StaffRole.doctor, department="Nevrologiya",
                phone="+998 91 222 3344", email="karimova@clinic.uz", status=StatusEnum.active,
                joined_date="2022-06-01", patients_count=98, schedule="Du-Jsh 10:00-18:00"),
    StaffMember(id="3", name="Malika Yusupova", role=StaffRole.nurse, department="Terapiya",
                phone="+998 93 333 4455", email="yusupova@clinic.uz", status=StatusEnum.active,
                joined_date="2024-03-10", patients_count=0, schedule="Du-Ju 08:00-16:00"),
    StaffMember(id="4", name="Jasur Mirzayev", role=StaffRole.receptionist, department="Qabul",
                phone="+998 94 444 5566", email="mirzayev@clinic.uz", status=StatusEnum.active,
                joined_date="2024-01-05", patients_count=0, schedule="Du-Sha 09:00-18:00"),
]

clinic_settings = ClinicSettings(
    clinic_name="Digital Clinic",
    address="Toshkent, Amir Temur ko'chasi 1",
    phone="+998 71 200 0000",
    email="info@digitalclinic.uz",
)

# ─────────────────────────────────────────────
#  Auth helpers
# ─────────────────────────────────────────────

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET o'rnatilmagan yoki juda qisqa (kamida 32 belgi). .env faylini tekshiring.")

def _create_token(user: dict, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user["email"], "uid": user["id"], "role": user["role"], "type": token_type,
               "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_access_token(user: dict) -> str:
    return _create_token(user, "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

def create_refresh_token(user: dict) -> str:
    return _create_token(user, "refresh", timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

def decode_token(token: str, expected_type: str) -> dict:
    """Tokenni tekshiradi; yaroqsiz, eskirgan yoki turi noto'g'ri bo'lsa 401."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM],
                             options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token yaroqsiz yoki muddati tugagan",
                            headers={"WWW-Authenticate": "Bearer"})
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Token turi noto'g'ri",
                            headers={"WWW-Authenticate": "Bearer"})
    return payload

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(credentials.credentials, "access")
    user = fake_users.get(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Token yaroqsiz yoki muddati tugagan",
                            headers={"WWW-Authenticate": "Bearer"})
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}

# ─────────────────────────────────────────────
#  LLM client (OpenAI-mos API: Groq, vLLM, ...)
# ─────────────────────────────────────────────

# false bo'lsa LLM'ga hech qanday tashqi so'rov yuborilmaydi, statik demo javoblar qaytariladi
AI_ENABLED = os.getenv("AI_ENABLED", "false").strip().lower() in ("1", "true", "yes")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "30"))

AI_DISCLAIMER = ("Bu AI yordamchi faqat ma'lumot maqsadida. "
                 "Professional tibbiy maslahat uchun shifokorga murojaat qiling.")
CHAT_SYSTEM_PROMPT = (
    "Sen Digital Clinic tizimining tibbiy AI yordamchisisan. O'zbek tilida qisqa, aniq va professional javob ber. "
    "Tibbiy terminologiyadan foydalanishing mumkin, lekin oddiy til bilan tushuntir. "
    "Har doim \"shifokorga murojaat qiling\" deb ta'kidla.")
ANALYZE_SYSTEM_PROMPT = (
    "Sen tibbiy klinika uchun analitik AI yordamchisisan. Berilgan statistika asosida qisqa (200-250 so'z) "
    "va amaliy tavsiyalar ber. O'zbek tilida yoz. Raqamli ma'lumotlarga asoslan.")

DEMO_CHAT_RESPONSES = {
    "qon": "Qon bosimi ko'tarilganda: darhol shifokorga murojaat qiling. Amlodipine yoki boshqa antihipertenziv dorilar buyurilishi mumkin.",
    "diabet": "Qandli diabetda qon shakarini nazorat qilish juda muhim. Metformin va diet terapiyasi ko'p qo'llaniladi.",
    "dori": "Dori buyurish uchun shifokor konsultatsiyasi zarur. Bemor anamnezini tekshiring.",
}
DEMO_CHAT_DEFAULT = "Bemorning holati kuzatuv ostida bo'lishi tavsiya etiladi. Qo'shimcha tekshiruvlar o'tkazish kerak bo'lishi mumkin."
DEMO_CHAT_SUGGESTIONS = [
    "Qo'shimcha qon tahlili buyuring",
    "Blood pressure monitoring tavsiya eting",
    "Ovqatlanish rejimini ko'rib chiqing",
]
DEMO_ANALYSIS = (
    "1) Asosiy xulosalar: bemorlar oqimi va daromad o'sish tendensiyasida.\n"
    "2) Muammoli joylar: uchrashuvlarning bekor qilinish ulushi yuqori.\n"
    "3) Tavsiyalar: SMS eslatmalar yuborish, eng band kunlarda qabul jadvalini kengaytirish, "
    "eng ko'p uchraydigan tashxislar bo'yicha profilaktika dasturini ishga tushirish.")

def call_llm(messages: list, temperature: float, max_tokens: int) -> str:
    """LLM'ga so'rov yuboradi; xatolarni mos HTTP statuslarga o'giradi."""
    if not LLM_API_KEY:
        raise HTTPException(status_code=503, detail="AI xizmati sozlanmagan (LLM_API_KEY)")
    try:
        res = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={"model": LLM_MODEL, "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens, "stream": False},
            timeout=LLM_TIMEOUT,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI xizmati javob bermadi (timeout)")
    except httpx.HTTPError as e:
        logger.error("LLM ulanish xatosi: %s", e)
        raise HTTPException(status_code=502, detail="AI xizmatiga ulanib bo'lmadi")
    if res.status_code != 200:
        logger.error("LLM xatosi %s: %s", res.status_code, res.text[:300])
        raise HTTPException(status_code=502, detail=f"AI xizmati xatosi (HTTP {res.status_code})")
    try:
        return res.json()["choices"][0]["message"]["content"] or "Javob olinmadi."
    except (KeyError, IndexError, ValueError):
        raise HTTPException(status_code=502, detail="AI xizmati noto'g'ri javob qaytardi")

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@app.get("/", tags=["Root"], summary="API sog'ligi tekshiruvi")
def root():
    """API ishlayotganini tekshirish uchun endpoint."""
    return {"status": "ok", "message": "Digital Clinic AI API", "docs": "/docs"}

# ── AUTH ──────────────────────────────────────
@app.post("/auth/login", tags=["🔐 Auth"], response_model=TokenResponse,
          summary="Tizimga kirish", description="Email va parol orqali tizimga kiring va JWT token oling.")
def login(data: LoginRequest):
    user = fake_users.get(data.email)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email yoki parol noto'g'ri")
    return TokenResponse(access_token=create_access_token(user), refresh_token=create_refresh_token(user), user={"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]})

@app.post("/auth/refresh", tags=["🔐 Auth"], response_model=TokenResponse,
          summary="Access tokenni yangilash",
          description="Refresh token (7 kun) bilan yangi access (30 daqiqa) va yangi refresh token oling.")
def refresh(data: RefreshRequest):
    payload = decode_token(data.refresh_token, "refresh")
    user = fake_users.get(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Token yaroqsiz yoki muddati tugagan")
    return TokenResponse(access_token=create_access_token(user), refresh_token=create_refresh_token(user),
                         user={"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]})

@app.post("/auth/register", tags=["🔐 Auth"], status_code=status.HTTP_201_CREATED,
          summary="Yangi hisob yaratish", description="Yangi klinika uchun admin hisob yarating.")
def register(data: RegisterRequest):
    if data.email in fake_users:
        raise HTTPException(status_code=400, detail="Bu email allaqachon ro'yxatdan o'tgan")
    fake_users[data.email] = {
        "id": str(len(fake_users) + 1), "name": data.name, "email": data.email,
        "password_hash": hash_password(data.password), "role": "admin"
    }
    return {"message": "Muvaffaqiyatli ro'yxatdan o'tdingiz", "email": data.email}

@app.post("/auth/forgot-password", tags=["🔐 Auth"],
          summary="Parolni tiklash (hozircha mavjud emas)", description="Email orqali tiklash hali amalga oshirilmagan; 501 qaytaradi.")
def forgot_password(data: ForgotPasswordRequest):
    # Email yuborish hozircha yo'q: yolg'on "yuborildi" javobi o'rniga halol 501
    raise HTTPException(status_code=501, detail="Parolni tiklash uchun administratorga murojaat qiling")

# ── PATIENTS ──────────────────────────────────
@app.get("/patients", tags=["👥 Patients"], response_model=List[Patient],
         summary="Barcha bemorlar ro'yxati",
         description="Barcha bemorlarni oling. Qidiruv va filtrlash imkoniyati mavjud.")
def get_patients(
    search: Optional[str] = Query(None, description="Ism bo'yicha qidiruv"),
    status: Optional[StatusEnum] = Query(None, description="Status bo'yicha filter"),
    skip: int = Query(0, ge=0, description="Nechta yozuvni o'tkazib yuborish"),
    limit: int = Query(10, ge=1, le=100, description="Nechta yozuv qaytarish"),
    _=Depends(get_current_user)
):
    results = fake_patients
    if search:
        results = [p for p in results if search.lower() in p.name.lower()]
    if status:
        results = [p for p in results if p.status == status]
    return results[skip:skip + limit]

@app.post("/patients", tags=["👥 Patients"], response_model=Patient,
          status_code=status.HTTP_201_CREATED,
          summary="Yangi bemor qo'shish", description="Yangi bemor ma'lumotlarini tizimga kiritish.")
def create_patient(data: PatientCreate, _=Depends(get_current_user)):
    patient = Patient(**data.dict(), id=str(len(fake_patients) + 1),
                      created_at=datetime.now().isoformat()[:10])
    fake_patients.append(patient)
    return patient

@app.get("/patients/{patient_id}", tags=["👥 Patients"], response_model=Patient,
         summary="Bemor ma'lumotlari", description="Bemor ID si orqali to'liq ma'lumot olish.")
def get_patient(patient_id: str, _=Depends(get_current_user)):
    patient = next((p for p in fake_patients if p.id == patient_id), None)
    if not patient:
        raise HTTPException(status_code=404, detail="Bemor topilmadi")
    return patient

@app.put("/patients/{patient_id}", tags=["👥 Patients"], response_model=Patient,
         summary="Bemor ma'lumotlarini yangilash")
def update_patient(patient_id: str, data: PatientUpdate, _=Depends(get_current_user)):
    for i, p in enumerate(fake_patients):
        if p.id == patient_id:
            updated = p.dict()
            updated.update({k: v for k, v in data.dict().items() if v is not None})
            fake_patients[i] = Patient(**updated)
            return fake_patients[i]
    raise HTTPException(status_code=404, detail="Bemor topilmadi")

@app.delete("/patients/{patient_id}", tags=["👥 Patients"],
            summary="Bemor o'chirish", description="Bemor yozuvini tizimdan o'chirish.")
def delete_patient(patient_id: str, _=Depends(get_current_user)):
    global fake_patients
    patient = next((p for p in fake_patients if p.id == patient_id), None)
    if not patient:
        raise HTTPException(status_code=404, detail="Bemor topilmadi")
    fake_patients = [p for p in fake_patients if p.id != patient_id]
    return {"message": "Bemor muvaffaqiyatli o'chirildi"}

# ── APPOINTMENTS ──────────────────────────────
@app.get("/appointments", tags=["📅 Appointments"], response_model=List[Appointment],
         summary="Uchrashuvlar ro'yxati", description="Barcha rejalashtirilgan uchrashuvlarni olish.")
def get_appointments(
    date: Optional[str] = Query(None, description="Sana bo'yicha filter (YYYY-MM-DD)"),
    doctor: Optional[str] = Query(None, description="Shifokor bo'yicha filter"),
    status: Optional[AppointmentStatus] = Query(None, description="Status bo'yicha filter"),
    _=Depends(get_current_user)
):
    results = fake_appointments
    if date:
        results = [a for a in results if a.date == date]
    if doctor:
        results = [a for a in results if doctor.lower() in a.doctor.lower()]
    if status:
        results = [a for a in results if a.status == status]
    return results

@app.post("/appointments", tags=["📅 Appointments"], response_model=Appointment,
          status_code=201, summary="Uchrashuv rejalashtirish")
def create_appointment(data: AppointmentCreate, _=Depends(get_current_user)):
    appt = Appointment(**data.dict(), id=str(len(fake_appointments) + 1),
                       created_at=datetime.now().isoformat()[:10])
    fake_appointments.append(appt)
    return appt

@app.patch("/appointments/{appt_id}/status", tags=["📅 Appointments"],
           summary="Uchrashuv statusini o'zgartirish")
def update_appointment_status(appt_id: str, status: AppointmentStatus, _=Depends(get_current_user)):
    for a in fake_appointments:
        if a.id == appt_id:
            a.status = status
            return a
    raise HTTPException(404, "Uchrashuv topilmadi")

@app.delete("/appointments/{appt_id}", tags=["📅 Appointments"], summary="Uchrashuvni bekor qilish")
def delete_appointment(appt_id: str, _=Depends(get_current_user)):
    global fake_appointments
    fake_appointments = [a for a in fake_appointments if a.id != appt_id]
    return {"message": "Uchrashuv bekor qilindi"}

# ── EMR ───────────────────────────────────────
@app.get("/emr", tags=["📋 EMR"], response_model=List[EMRRecord],
         summary="Tibbiy yozuvlar ro'yxati",
         description="Barcha elektron tibbiy yozuvlarni (EMR) olish.")
def get_emr(patient_id: Optional[str] = Query(None), _=Depends(get_current_user)):
    if patient_id:
        return [r for r in fake_emr if r.patient_id == patient_id]
    return fake_emr

@app.post("/emr", tags=["📋 EMR"], response_model=EMRRecord, status_code=201,
          summary="Yangi tibbiy yozuv qo'shish")
def create_emr(data: EMRCreate, _=Depends(get_current_user)):
    record = EMRRecord(**data.dict(), id=str(len(fake_emr) + 1),
                       created_at=datetime.now().isoformat()[:10])
    fake_emr.append(record)
    return record

@app.get("/emr/{record_id}", tags=["📋 EMR"], response_model=EMRRecord,
         summary="Bitta tibbiy yozuv")
def get_emr_record(record_id: str, _=Depends(get_current_user)):
    record = next((r for r in fake_emr if r.id == record_id), None)
    if not record:
        raise HTTPException(404, "Yozuv topilmadi")
    return record

# ── FINANCE ───────────────────────────────────
@app.get("/finance/transactions", tags=["💰 Finance"], response_model=List[Transaction],
         summary="Moliyaviy tranzaksiyalar", description="Barcha daromad va xarajatlarni ko'rish.")
def get_transactions(
    type: Optional[TransactionType] = Query(None),
    category: Optional[str] = Query(None),
    _=Depends(get_current_user)
):
    results = fake_transactions
    if type:
        results = [t for t in results if t.type == type]
    if category:
        results = [t for t in results if t.category == category]
    return results

@app.post("/finance/transactions", tags=["💰 Finance"], response_model=Transaction, status_code=201,
          summary="Yangi tranzaksiya qo'shish")
def create_transaction(data: TransactionCreate, _=Depends(get_current_user)):
    tx = Transaction(**data.dict(), id=str(len(fake_transactions) + 1),
                     created_at=datetime.now().isoformat()[:10])
    fake_transactions.append(tx)
    return tx

@app.get("/finance/summary", tags=["💰 Finance"],
         summary="Moliyaviy xulosа",
         description="Jami daromad, xarajat va foyda ko'rsatkichlarini olish.")
def get_finance_summary(_=Depends(get_current_user)):
    income = sum(t.amount for t in fake_transactions if t.type == TransactionType.income)
    expense = sum(t.amount for t in fake_transactions if t.type == TransactionType.expense)
    return {
        "total_income": income,
        "total_expense": expense,
        "net_profit": income - expense,
        "currency": "UZS",
        "period": "2026-02",
        "transactions_count": len(fake_transactions)
    }

# ── ANALYTICS ─────────────────────────────────
@app.get("/analytics/dashboard", tags=["📊 Analytics"],
         summary="Dashboard statistikasi",
         description="Asosiy dashboard ko'rsatkichlari: bemorlar, uchrashuvlar, daromad.")
def get_dashboard_stats(_=Depends(get_current_user)):
    return {
        "total_patients": 1284,
        "total_appointments_today": 42,
        "monthly_revenue": 48250000,
        "active_doctors": 18,
        "revenue_change": "+12.5%",
        "patients_change": "+3.2%",
        "appointments_change": "-5.1%",
        "doctors_change": "+2",
        "revenue_chart": [
            {"month": "Sep", "value": 35000000},
            {"month": "Oct", "value": 42000000},
            {"month": "Nov", "value": 38000000},
            {"month": "Dec", "value": 45000000},
            {"month": "Jan", "value": 41000000},
            {"month": "Feb", "value": 48250000},
        ],
        "patient_flow": [
            {"day": "Du", "new": 12, "returning": 28},
            {"day": "Se", "new": 8, "returning": 32},
            {"day": "Ch", "new": 15, "returning": 25},
            {"day": "Pa", "new": 10, "returning": 30},
            {"day": "Ju", "new": 18, "returning": 22},
        ]
    }

@app.get("/analytics/reports", tags=["📊 Analytics"],
         summary="Tahliliy hisobotlar",
         description="Bemorlar, daromad, shifokorlar bo'yicha tahliliy ma'lumotlar.")
def get_analytics(_=Depends(get_current_user)):
    return {
        "top_diagnoses": [
            {"name": "Gipertenziya", "count": 234},
            {"name": "Qandli diabet", "count": 187},
            {"name": "Ortopedik muammolar", "count": 143},
            {"name": "Nafas yo'llari kasalliklari", "count": 98},
        ],
        "top_doctors": [
            {"name": "Dr. Rustamov", "patients": 124, "rating": 4.9},
            {"name": "Dr. Karimov", "patients": 98, "rating": 4.8},
            {"name": "Dr. Yusupov", "patients": 87, "rating": 4.7},
        ],
        "patient_demographics": {
            "male": 48, "female": 52,
            "age_groups": {"0-18": 12, "19-35": 28, "36-55": 38, "55+": 22}
        }
    }

# ── AI ASSISTANT ──────────────────────────────
@app.post("/ai/chat", tags=["🤖 AI Assistant"],
          summary="AI yordamchi bilan suhbat",
          description="""
Tibbiy savollarga AI yordamchidan javob oling.

⚠️ **Muhim**: Bu AI yordamchi professional tibbiy maslahatni almashtirmaydi.
Faqat ma'lumot olish maqsadida foydalaning.
          """,
          response_model=AIResponse)
def ai_chat(data: AIMessage, _=Depends(get_current_user)):
    if not AI_ENABLED:
        text = next((v for k, v in DEMO_CHAT_RESPONSES.items() if k in data.message.lower()), DEMO_CHAT_DEFAULT)
        return AIResponse(response=text, demo=True, suggestions=DEMO_CHAT_SUGGESTIONS, disclaimer=AI_DISCLAIMER)
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    if data.context:
        messages.append({"role": "system", "content": f"Kontekst: {data.context}"})
    messages += [t.model_dump() for t in data.history[-10:]]
    messages.append({"role": "user", "content": data.message})
    text = call_llm(messages, temperature=0.7, max_tokens=1024)
    return AIResponse(response=text, suggestions=[], disclaimer=AI_DISCLAIMER)

@app.get("/ai/status", tags=["🤖 AI Assistant"], summary="AI rejimi (demo yoki LLM)")
def ai_status(_=Depends(get_current_user)):
    return {"enabled": AI_ENABLED, "demo": not AI_ENABLED}

@app.post("/ai/analyze", tags=["🤖 AI Assistant"], response_model=AnalyzeResponse,
          summary="Klinika statistikasini AI bilan tahlil qilish")
def ai_analyze(data: AnalyzeRequest, _=Depends(get_current_user)):
    if not AI_ENABLED:
        return AnalyzeResponse(analysis=DEMO_ANALYSIS, demo=True, disclaimer=AI_DISCLAIMER)
    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Quyidagi klinika statistikasini ({data.period}) tahlil qil va amaliy tavsiyalar ber:\n"
            f"{data.stats}\n\nQuyidagilarni ko'rsat: 1) Asosiy xulosalar 2) Muammoli joylar 3) Konkret tavsiyalar")},
    ]
    text = call_llm(messages, temperature=0.6, max_tokens=600)
    return AnalyzeResponse(analysis=text, disclaimer=AI_DISCLAIMER)

@app.get("/ai/insights", tags=["🤖 AI Assistant"],
         summary="AI tahliliy ma'lumotlar",
         description="Klinika ma'lumotlari asosida AI tavsiyalari.")
def get_ai_insights(_=Depends(get_current_user)):
    return {
        "insights": [
            {"type": "warning", "title": "Yuqori bekor qilishlar", "message": "Bu oyda 23% uchrashuvlar bekor qilindi. SMS eslatmalar yuborish tavsiya etiladi."},
            {"type": "success", "title": "Daromad o'sishi", "message": "Oxirgi oyga nisbatan 12.5% o'sish kuzatildi."},
            {"type": "info", "title": "Eng ko'p murojaat", "message": "Seshanba va Chorshanba kunlari eng ko'p bemor keladi."},
        ]
    }

# ── STAFF ─────────────────────────────────────
@app.get("/staff", tags=["👔 Staff"], response_model=List[StaffMember],
         summary="Xodimlar ro'yxati", description="Barcha klinika xodimlarini ko'rish.")
def get_staff(role: Optional[StaffRole] = None, _=Depends(get_current_user)):
    if role:
        return [s for s in fake_staff if s.role == role]
    return fake_staff

@app.post("/staff", tags=["👔 Staff"], response_model=StaffMember, status_code=201,
          summary="Yangi xodim qo'shish")
def create_staff(data: StaffCreate, _=Depends(get_current_user)):
    member = StaffMember(**data.dict(), id=str(len(fake_staff) + 1),
                         joined_date=datetime.now().isoformat()[:10])
    fake_staff.append(member)
    return member

@app.delete("/staff/{staff_id}", tags=["👔 Staff"], summary="Xodimni o'chirish")
def delete_staff(staff_id: str, _=Depends(get_current_user)):
    global fake_staff
    fake_staff = [s for s in fake_staff if s.id != staff_id]
    return {"message": "Xodim o'chirildi"}

# ── SETTINGS ──────────────────────────────────
@app.get("/settings", tags=["⚙️ Settings"], response_model=ClinicSettings,
         summary="Klinika sozlamalari", description="Joriy klinika sozlamalarini olish.")
def get_settings(_=Depends(get_current_user)):
    return clinic_settings

@app.put("/settings", tags=["⚙️ Settings"], response_model=ClinicSettings,
         summary="Sozlamalarni yangilash")
def update_settings(data: ClinicSettings, _=Depends(get_current_user)):
    global clinic_settings
    clinic_settings = data
    return clinic_settings

# ── REPORTS ───────────────────────────────────
@app.get("/reports", tags=["📝 Reports"],
         summary="Hisobotlar ro'yxati",
         description="Mavjud hisobot shablonlarini ko'rish.")
def get_reports(_=Depends(get_current_user)):
    return {
        "reports": [
            {"id": "1", "name": "Oylik moliyaviy hisobot", "type": "finance", "last_generated": "2026-02-01"},
            {"id": "2", "name": "Bemorlar statistikasi", "type": "patients", "last_generated": "2026-02-15"},
            {"id": "3", "name": "Xodimlar faoliyati", "type": "staff", "last_generated": "2026-02-20"},
            {"id": "4", "name": "Uchrashuvlar tahlili", "type": "appointments", "last_generated": "2026-02-22"},
        ]
    }

@app.post("/reports/generate/{report_id}", tags=["📝 Reports"],
          summary="Hisobot generatsiya qilish",
          description="Berilgan ID bo'yicha hisobot yaratish va yuklash havolasini olish.")
def generate_report(report_id: str, _=Depends(get_current_user)):
    return {
        "status": "generated",
        "report_id": report_id,
        "download_url": f"/reports/download/{report_id}",
        "generated_at": datetime.now().isoformat(),
        "format": "CSV"
    }

REPORT_SOURCES = {
    "1": ("moliyaviy_hisobot", lambda: fake_transactions),
    "2": ("bemorlar_statistikasi", lambda: fake_patients),
    "3": ("xodimlar_faoliyati", lambda: fake_staff),
    "4": ("uchrashuvlar_tahlili", lambda: fake_appointments),
}

def _csv_cell(value):
    # CSV/formula injection'dan himoya: =, +, -, @ bilan boshlanuvchi matnlar
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text

@app.get("/reports/download/{report_id}", tags=["📝 Reports"],
         summary="Hisobotni CSV sifatida yuklab olish",
         description="UTF-8 BOM bilan CSV (Excel to'g'ri ochadi). Authorization header talab qilinadi.")
def download_report(report_id: str, _=Depends(get_current_user)):
    if report_id not in REPORT_SOURCES:
        raise HTTPException(status_code=404, detail="Hisobot topilmadi")
    name, source = REPORT_SOURCES[report_id]
    rows = [r.model_dump(mode="json") for r in source()]
    buf = io.StringIO()
    writer = csv.writer(buf)
    if rows:
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow([_csv_cell(v) for v in r.values()])
    content = "\ufeff" + buf.getvalue()
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}_{date.today().isoformat()}.csv"'},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
