"""Ruxsatlar katalogi va standart rollar matritsasi.

Rollar va ularning ruxsatlari bazada saqlanadi (roles, permissions, role_permissions);
bu yerdagi matritsa faqat bo'sh bazaga birinchi marta yuklanadigan boshlang'ich holat.
"""

PERMISSIONS: dict[str, str] = {
    "patients:read": "Bemorlarni ko'rish",
    "patients:write": "Bemor qo'shish va tahrirlash",
    "patients:delete": "Bemorni o'chirish",
    "patients:merge": "Bemor dublikatlarini birlashtirish",
    "appointments:read": "Uchrashuvlarni ko'rish",
    "appointments:write": "Uchrashuv yozish va o'zgartirish",
    "appointments:override": "Ish vaqtidan tashqari majburan yozish (sabab bilan; band vaqtga emas)",
    "emr:read": "Tibbiy yozuvlarni (EMR) ko'rish",
    "emr:write": "Tibbiy yozuv va retsept yozish",
    "lab:read": "Laboratoriya buyurtma va natijalarini ko'rish",
    "lab:write": "Laboratoriya buyurtma berish va natija kiritish",
    "services:read": "Narxnomani (xizmatlar) ko'rish",
    "services:write": "Narxnomani o'zgartirish (narx, MXIK, QQS)",
    "finance:read": "Moliyani ko'rish",
    "finance:write": "To'lov va tranzaksiya kiritish",
    "finance:discount": "Hisob-fakturaga chegirma berish",
    "finance:refund": "To'lovni qaytarish",
    "commissions:read": "Shifokor foizi hisobotini ko'rish (o'zingiznikini; boshqarish ruxsati bilan hammasini)",
    "commissions:manage": "Shifokor foizi qoidalari va oylik hisob-kitob",
    "staff:read": "Xodimlarni ko'rish",
    "staff:write": "Xodimlarni boshqarish",
    "settings:read": "Klinika sozlamalarini ko'rish",
    "settings:write": "Klinika sozlamalarini o'zgartirish",
    "analytics:read": "Dashboard va tahlil",
    "reports:read": "Hisobotlarni yuklab olish",
    "ai:use": "AI yordamchidan foydalanish",
    "audit:read": "Audit jurnalini ko'rish",
    "roles:manage": "Rollar va ruxsatlarni boshqarish",
}

ROLES: dict[str, tuple[str, list[str]]] = {
    "admin": ("Administrator", list(PERMISSIONS)),
    "doctor": ("Shifokor", [
        "patients:read", "patients:write", "appointments:read", "appointments:write",
        "emr:read", "emr:write", "lab:read", "lab:write", "services:read", "commissions:read", "staff:read",
        "settings:read", "analytics:read", "reports:read", "ai:use",
    ]),
    "nurse": ("Hamshira", [
        "patients:read", "patients:write", "appointments:read", "appointments:write",
        "emr:read", "lab:read", "lab:write", "staff:read", "settings:read", "ai:use",
    ]),
    "receptionist": ("Qabulxona", [
        "patients:read", "patients:write", "patients:merge", "appointments:read", "appointments:write",
        "services:read", "staff:read", "settings:read",
    ]),
    "cashier": ("Kassir", [
        "patients:read", "appointments:read", "finance:read", "finance:write", "finance:discount", "services:read",
        "staff:read", "settings:read", "analytics:read", "reports:read",
    ]),
    "senior_receptionist": ("Katta registrator", [
        "patients:read", "patients:write", "patients:merge", "appointments:read", "appointments:write",
        "appointments:override", "services:read", "staff:read", "settings:read",
    ]),
}
