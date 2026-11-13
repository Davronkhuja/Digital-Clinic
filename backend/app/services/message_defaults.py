# ruff: noqa: E501
"""Standart xabar shablonlari (o'zbek lotin, rus). Sozlamalarda tahrirlanadi (message_templates); bu yerdagilar boshlang'ich/zaxira.
SMS uchun lotin matnda oddiy apostrof (') ishlatiladi: GSM-7 sig'imi (160) saqlanadi."""

DEFAULTS: dict[tuple[str, str], str] = {
    ("reminder_24h", "uz"): "{clinic}: {patient}, ertaga {time} da {doctor} qabuliga yozilgansiz ({date}). Tasdiqlash yoki bekor qilish: {link}",
    ("reminder_24h", "ru"): "{clinic}: {patient}, завтра в {time} у вас приём к {doctor} ({date}). Подтвердить или отменить: {link}",
    ("reminder_2h", "uz"): "{clinic}: {patient}, 2 soatdan keyin ({time}) {doctor} qabuli. Bekor qilish: {link}",
    ("reminder_2h", "ru"): "{clinic}: {patient}, через 2 часа ({time}) приём к {doctor}. Отменить: {link}",
    ("otp", "uz"): "{clinic}: tasdiqlash kodi {code}. Kodni hech kimga bermang.",
    ("otp", "ru"): "{clinic}: код подтверждения {code}. Никому не сообщайте код.",
    ("booking_confirmation", "uz"): "{clinic}: {patient}, siz {date} {time} da {doctor} qabuliga yozildingiz. Tasdiqlash/bekor qilish: {link}",
    ("booking_confirmation", "ru"): "{clinic}: {patient}, вы записаны на {date} в {time} к {doctor}. Подтвердить/отменить: {link}",
    ("waitlist_offer", "uz"): "{clinic}: {patient}, {doctor} da bo'sh vaqt paydo bo'ldi: {date} {time}. Band qilish: {link}",
    ("waitlist_offer", "ru"): "{clinic}: {patient}, освободилось время у {doctor}: {date} {time}. Записаться: {link}",
    ("recall", "uz"): "{clinic}: {patient}, {doctor} belgilagan takroriy ko'rik vaqti keldi. Yozilish: {link}",
    ("recall", "ru"): "{clinic}: {patient}, пора на повторный приём, назначенный {doctor}. Запись: {link}",
}
KEYS = sorted({k for k, _ in DEFAULTS})
LANGUAGES = ("uz", "ru")
