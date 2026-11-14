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
    "lab:approve": "Laboratoriya natijalarini bemorga ko'rinadigan qilib tasdiqlash (shifokor)",
    "lab:write": "Laboratoriya buyurtma berish va natija kiritish",
    "services:read": "Narxnomani (xizmatlar) ko'rish",
    "services:write": "Narxnomani o'zgartirish (narx, MXIK, QQS)",
    "finance:read": "Moliyani ko'rish",
    "finance:write": "To'lov va tranzaksiya kiritish",
    "finance:discount": "Hisob-fakturaga chegirma berish (sozlamadagi limitgacha)",
    "finance:discount_override": "Limitdan ortiq chegirma berish",
    "finance:refund": "To'lovni qaytarish",
    "finance:cash_withdrawal": "Kassadan inkassatsiya (naqd chiqarish)",
    "finance:shifts": "Hamma kassa smenalarini ko'rish va boshqa kassir smenasini yopish",
    "commissions:read": "Shifokor foizi hisobotini ko'rish (o'zingiznikini; boshqarish ruxsati bilan hammasini)",
    "commissions:pay": "Shifokor foizi to'lovini bajarish (naqd/o'tkazma)",
    "commissions:manage": "Shifokor foizi qoidalari va oylik hisob-kitob",
    "branches:manage": "Filiallarni qo'shish, o'zgartirish va foydalanuvchini filialga biriktirish",
    "branches:all": "Boshqa filialga o'tib ishlash (faol filialni almashtirish)",
    "warehouse:read": "Ombor: katalog, qoldiq va ogohlantirishlarni ko'rish",
    "warehouse:write": "Ombor: katalog, kirim, chiqim va hisobdan chiqarish",
    "warehouse:approve": "Ombor: inventarizatsiya farqini tasdiqlash (avtomatik kirim/chiqim yoziladi)",
    "warehouse:transfer": "Ombor: filiallar orasida ko'chirish hujjatini yuborish, qabul qilish va bekor qilish",
    "staff:read": "Xodimlarni ko'rish",
    "staff:write": "Xodimlarni boshqarish",
    "settings:read": "Klinika sozlamalarini ko'rish",
    "settings:write": "Klinika sozlamalarini o'zgartirish",
    "analytics:read": "Dashboard va tahlil",
    "reports:read": "Hisobotlarni yuklab olish",
    "ai:use": "AI yordamchidan foydalanish",
    "messages:read": "Xabarlar logi va SMS hisobini ko'rish",
    "exports:read": "Buxgalteriya eksporti (sotuvlar, to'lovlar, kassa smenalari, ombor harakatlari, shifokor foizlari): Excel va CSV",
    "audit:read": "Audit jurnalini ko'rish",
    "roles:manage": "Rollar va ruxsatlarni boshqarish",
}

ROLES: dict[str, tuple[str, list[str]]] = {
    "admin": ("Administrator", list(PERMISSIONS)),
    "doctor": ("Shifokor", [
        "patients:read", "patients:write", "appointments:read", "appointments:write",
        "emr:read", "emr:write", "lab:read", "lab:write", "lab:approve", "services:read", "commissions:read", "staff:read",
        "warehouse:read",
        "settings:read", "analytics:read", "reports:read", "ai:use",
    ]),
    "nurse": ("Hamshira", [
        "patients:read", "patients:write", "appointments:read", "appointments:write",
        "emr:read", "lab:read", "lab:write", "staff:read", "settings:read", "ai:use",
        "warehouse:read", "warehouse:write", "warehouse:transfer",
    ]),
    "receptionist": ("Qabulxona", [
        "patients:read", "patients:write", "patients:merge", "appointments:read", "appointments:write",
        "services:read", "messages:read", "staff:read", "settings:read",
    ]),
    "cashier": ("Kassir", [
        "patients:read", "appointments:read", "finance:read", "finance:write", "finance:discount", "services:read",
        "staff:read", "settings:read", "analytics:read", "reports:read",
    ]),
    "senior_receptionist": ("Katta registrator", [
        "patients:read", "patients:write", "patients:merge", "appointments:read", "appointments:write",
        "appointments:override", "services:read", "messages:read", "staff:read", "settings:read",
    ]),
}
