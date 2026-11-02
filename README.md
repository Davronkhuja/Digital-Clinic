# 🏥 Digital Clinic AI

Vue 3 + Python FastAPI asosida qurilgan zamonaviy klinika boshqaruv tizimi.

---

## 📁 Loyiha tuzilmasi

```
digital-clinic/
├── backend/          ← Python FastAPI backend
│   ├── main.py       ← Asosiy API fayl
│   └── requirements.txt
└── frontend/         ← Vue 3 frontend
    ├── src/
    │   ├── views/    ← Sahifalar
    │   ├── components/ ← Komponentlar
    │   ├── stores/   ← Pinia stores
    │   ├── router/   ← Vue Router
    │   └── composables/ ← Axios API
    └── package.json
```

---

## 🚀 Ishga tushirish

### 1. Backend (Python FastAPI)

```bash
cd backend

# Virtual muhit yarating (ixtiyoriy lekin tavsiya etiladi)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# yoki
venv\Scripts\activate  # Windows

# Kutubxonalarni o'rnating
pip install -r requirements.txt

# Serverni ishga tushiring
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend ishlayotganda:
- **API**: http://localhost:8000
- **Swagger UI (Docs)**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 2. Frontend (Vue 3)

```bash
cd frontend

# Paketlarni o'rnating
npm install

# Dev serverni ishga tushiring
npm run dev
```

Frontend: http://localhost:5173

---

## 🔐 Demo kirish

| Email | Parol |
|-------|-------|
| admin@clinic.uz | password123 |

---

## 📋 API Endpointlar

| Bo'lim | URL |
|--------|-----|
| 🔐 Auth | `/auth/login`, `/auth/register`, `/auth/forgot-password` |
| 👥 Bemorlar | `/patients` (GET, POST, PUT, DELETE) |
| 📅 Uchrashuvlar | `/appointments` (GET, POST, PATCH, DELETE) |
| 📋 EMR | `/emr` (GET, POST) |
| 💰 Moliya | `/finance/transactions`, `/finance/summary` |
| 📊 Tahlil | `/analytics/dashboard`, `/analytics/reports` |
| 🤖 AI | `/ai/chat`, `/ai/insights` |
| 👔 Xodimlar | `/staff` (GET, POST, DELETE) |
| 📝 Hisobotlar | `/reports`, `/reports/generate/{id}` |
| ⚙️ Sozlamalar | `/settings` (GET, PUT) |

**To'liq hujjatlar**: http://localhost:8000/docs

---

## 🛠️ Texnologiyalar

| Frontend | Backend |
|----------|---------|
| Vue 3 + Composition API | Python 3.11+ |
| Vue Router 4 | FastAPI 0.111 |
| Pinia (State) | Pydantic v2 |
| Axios (HTTP) | Uvicorn |
| Tailwind CSS | Swagger/OpenAPI |
| Lucide Icons | |

---

## 📱 Sahifalar

- **Dashboard** — Statistika, grafiklar, AI tavsiyalar
- **Bemorlar** — CRUD, qidiruv, export CSV
- **Uchrashuvlar** — Rejalashtirish, status boshqaruvi
- **EMR** — Elektron tibbiy yozuvlar
- **Moliya** — Daromad/xarajat tranzaksiyalari
- **Tahlil** — Tashxis, shifokor, demografiya statistikasi
- **AI Yordamchi** — Chat interfeysli AI konsultant
- **Hisobotlar** — PDF hisobot generatsiyasi
- **Xodimlar** — Staff boshqaruvi
- **Obuna** — Reja tanlash
- **Xavfsizlik** — Parol, 2FA
- **Sozlamalar** — Klinika ma'lumotlari
