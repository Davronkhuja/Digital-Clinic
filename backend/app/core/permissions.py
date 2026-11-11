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
    "emr:read": "Tibbiy yozuvlarni (EMR) ko'rish",
    "emr:write": "Tibbiy yozuv va retsept yozish",
    "lab:read": "Laboratoriya buyurtma va natijalarini ko'rish",
    "lab:write": "Laboratoriya buyurtma berish va natija kiritish",
    "finance:read": "Moliyani ko'rish",
    "finance:write": "To'lov va tranzaksiya kiritish",
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
        "emr:read", "emr:write", "lab:read", "lab:write", "staff:read", "settings:read", "analytics:read",
        "reports:read", "ai:use",
    ]),
    "nurse": ("Hamshira", [
        "patients:read", "patients:write", "appointments:read", "appointments:write",
        "emr:read", "lab:read", "lab:write", "staff:read", "settings:read", "ai:use",
    ]),
    "receptionist": ("Qabulxona", [
        "patients:read", "patients:write", "patients:merge", "appointments:read", "appointments:write",
        "staff:read", "settings:read",
    ]),
    "cashier": ("Kassir", [
        "patients:read", "appointments:read", "finance:read", "finance:write",
        "staff:read", "settings:read", "analytics:read", "reports:read",
    ]),
}
