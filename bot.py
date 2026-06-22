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
    "Отныне каждое твоё усилие — тренировка, шаг, приём пищи — фиксируется "
    "и превращается в опыт. Уровень, ранг, статы — всё растёт от твоих "
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
