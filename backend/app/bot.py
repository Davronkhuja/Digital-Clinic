# ruff: noqa: E501
"""Telegram bot (lokalda long polling). Transport: aiogram; mantiq `services/telegram_bot.py` da (testlanadi).
Ishga tushirish: `python -m app.bot` (docker compose xizmati `bot`). Token faqat .env da (TELEGRAM_BOT_TOKEN)."""
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.core.config import settings
from app.db.session import SessionLocal
from app.services import telegram_bot as logic

log = logging.getLogger("clinic.bot")
dp = Dispatcher()


def _markup(reply: logic.Reply):
    if reply.request_contact:
        return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=logic.CONTACT_BUTTON, request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
    if reply.buttons:
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in reply.buttons])
    return ReplyKeyboardRemove()


async def _run(fn, *args):
    return await asyncio.to_thread(_with_db, fn, *args)


def _with_db(fn, *args):
    with SessionLocal() as db:
        return fn(db, *args)


@dp.message(CommandStart())
async def on_start(message: Message):
    reply = await _run(logic.start, str(message.chat.id))
    await message.answer(reply.text, reply_markup=_markup(reply))


@dp.message(F.contact)
async def on_contact(message: Message):
    c = message.contact
    reply = await _run(logic.contact, str(message.chat.id), message.from_user.id, c.user_id, c.phone_number)
    await message.answer(reply.text, reply_markup=_markup(reply))


@dp.message(F.text)
async def on_text(message: Message):
    reply = await _run(logic.text, str(message.chat.id), message.text)
    await message.answer(reply.text, reply_markup=_markup(reply))


@dp.callback_query()
async def on_callback(query: CallbackQuery):
    reply = await _run(logic.callback, str(query.message.chat.id), query.data or "")
    await query.message.answer(reply.text)
    await query.answer()


async def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN .env da yo'q: bot ishga tushmaydi (BotFather'dan token oling)")
    logging.basicConfig(level=logging.INFO)
    bot = Bot(settings.telegram_bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
