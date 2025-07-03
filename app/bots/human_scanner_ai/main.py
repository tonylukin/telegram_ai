from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
import aiohttp

from app.config import TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, APP_HOST
from app.configs.logger import logger

USERNAME, CHATS, CONFIRM = range(3)

user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data[update.effective_chat.id] = {}
    intro_text = "👋 Привет! Этот бот дает описание человека на основе его активности в тех или иных каналах.\n Введите username (@ivan), если есть, либо полное имя аккаунта (Иван Иванов):"
    await update.message.reply_text(intro_text)
    return USERNAME

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data[chat_id]['username'] = update.message.text

    await update.message.reply_text("Теперь введите список чатов (через запятую: @chat1, https://t.me/chat2, t.me/+инвайт).\n Чаты должны быть публичными, это может быть канал с комментариями или просто домовой чат:")
    return CHATS

async def get_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chats = [c.strip() for c in update.message.text.split(',') if c.strip()]
    user_data[chat_id]['chats'] = chats

    username = user_data[chat_id]['username']
    summary = f"🔎 Вы ввели:\nUsername: `{username}`\nЧаты:\n" + '\n'.join(f"- `{c}`" for c in chats)
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")],
        [InlineKeyboardButton("🔁 Изменить", callback_data="restart")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel")],
    ]
    await update.message.reply_text(summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "confirm":
        await query.edit_message_text("⏳ Запрос отправляется... (если получите ошибку - просто попробуйте еще раз)")

        payload = {
            "username": user_data[chat_id]['username'],
            "chats": user_data[chat_id]['chats'],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{APP_HOST}/user-info/collect", json=payload) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        desc = result["result"].get("description", "Нет описания.")
                        await query.message.reply_text(f"📄 Результат:\n\n{desc}")
                    else:
                        await query.message.reply_text(f"⚠️ Ошибка сервера: {resp.status} {await resp.text()}")
        except Exception as e:
            await query.message.reply_text(f"❌ Ошибка при запросе:\n{str(e)}")

        return ConversationHandler.END

    elif query.data == "restart":
        await query.message.reply_text("🔄 Давайте начнём заново. Введите username:")
        return USERNAME

    elif query.data == "cancel":
        await query.message.reply_text("🚫 Операция отменена.")
        return ConversationHandler.END

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Операция отменена.")
    return ConversationHandler.END

# Основной запуск
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            CHATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_chats)],
            CONFIRM: [CallbackQueryHandler(handle_confirmation)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.run_polling()
