"""Опциональный live-бот — только для команды /start (приветствие + кнопка).

Периодические задачи (напоминания о неактивности, пуш по заявкам в
друзья) теперь НЕ здесь — они переехали в GitHub Actions
(.github/workflows/bot-*.yml), которые запускают scripts/check_*.py по
расписанию без необходимости держать сервер 24/7.

Сама кнопка «Открыть Систему» в меню бота уже настроена через
setChatMenuButton и работает всегда, даже если этот процесс не запущен —
запускать bot.py нужно только если хочешь, чтобы /start отвечал текстом.
"""

import os
import logging

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
APP_URL = "https://khlopenik.github.io/solo-leveling/"

logging.basicConfig(level=logging.INFO)

WELCOME_TEXT = (
    "⟢ СИСТЕМА ⟢\n\n"
    "Слабый Охотник, ты пробуждён.\n\n"
    "Отныне каждое твоё усилие: тренировка, шаг, приём пищи, фиксируется "
    "и превращается в опыт. Уровень, ранг, статы, всё растёт от твоих "
    "реальных действий.\n\n"
    "Нажми кнопку ниже, чтобы войти в Систему."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("⚔ Войти в Систему", web_app=WebAppInfo(url=APP_URL))]]
    )
    await update.message.reply_text(WELCOME_TEXT, reply_markup=keyboard)


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()


if __name__ == "__main__":
    main()
