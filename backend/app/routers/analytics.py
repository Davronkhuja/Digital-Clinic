from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, require

router = APIRouter()

# ── ANALYTICS ─────────────────────────────────
@router.get("/analytics/dashboard", tags=["📊 Analytics"],
         summary="Dashboard statistikasi",
         description="Asosiy dashboard ko'rsatkichlari: bemorlar, uchrashuvlar, daromad.")
def get_dashboard_stats(user: CurrentUser = Depends(require("analytics:read"))):
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

@router.get("/analytics/reports", tags=["📊 Analytics"],
         summary="Tahliliy hisobotlar",
         description="Bemorlar, daromad, shifokorlar bo'yicha tahliliy ma'lumotlar.")
def get_analytics(user: CurrentUser = Depends(require("analytics:read"))):
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
