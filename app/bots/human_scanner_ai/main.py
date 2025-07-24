from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
import aio_pika
import json

from app.config import TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, APP_HOST, RABBITMQ_QUEUE_HUMAN_SCANNER, API_TOKEN
from app.configs.logger import logger
from app.config import RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_HOST

MENU, USERNAME, CHATS, CONFIRM = range(4)
LOGGER_PREFIX = 'HumanScannerBot'
user_data = {}

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        message = update.message
    elif update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
    else:
        # fallback
        return None

    chat_id = message.chat.id
    user_data[chat_id] = {}

    keyboard = [
        [InlineKeyboardButton("🔎 HumanScan", callback_data="human_scan")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="info")]
    ]
    intro_text = (
        "👋 Привет! Этот бот дает описание человека на основе его активности в указанных каналах.\n"
        "У бота есть ограничения, поэтому будет использована активность за последнее время.\n"
        "Выберите действие:\n"
    )
    await message.reply_text(
        intro_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MENU


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "human_scan":
        user_data[chat_id] = {}
        await query.message.reply_text(
            "Введите username (@ivan), если есть, либо полное имя аккаунта (Иван Иванов), либо текст сообщения в группе:"
        )
        return USERNAME

    elif query.data == "info":
        await query.message.reply_text(
"""🔎 Хотите узнать больше о пользователе Telegram?
Теперь это проще, чем когда-либо! Наш бот поможет найти информацию по человеку, если вы знаете хотя бы его имя и чаты, где он состоит.

✨ Как это работает?
Вы указываете:

Никнейм (@username) или имя пользователя

Один или несколько чатов, где он может быть

📌 Поиск возможен по:

Никнейму чата (@chatname)

Ссылке на чат

Пригласительной ссылке

Просто названию чата (даже частичному — бот сам найдет совпадения)

🎯 Чем точнее вы укажете имя, тем выше шанс найти нужного человека.
Если в одном чате есть несколько пользователей с одинаковыми именами — возможны неточности, но бот покажет все совпадения.

💬 Проверить можно хоть 1 чат, хоть 100 — ограничений нет!

🚀 Убедитесь сами, насколько это удобно.
Подключайтесь и находите нужных людей в Telegram — быстро, просто и эффективно."""
        )
        return await show_menu_again(query, context)


async def show_menu_again(query, context):
    keyboard = [
        [InlineKeyboardButton("🔎 HumanScan", callback_data="human_scan")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="info")]
    ]
    await query.message.reply_text(
        "Что делаем дальше?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MENU

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await menu(update, context)

async def restart(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    return await menu(update_or_query, context)

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data[chat_id]['username'] = update.message.text

    await update.message.reply_text(
        "Теперь введите список чатов, где у юзера есть активность (через запятую: @chat1, https://t.me/chat2, t.me/+инвайт, либо название для поиска).\n"
        "Поддерживаются каналы (и их чаты) и обычные чаты.\n"
        "Чаты/каналы должны быть публичными (либо нужна ссылка-приглашение)."
    )
    return CHATS


async def get_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chats = [c.strip() for c in update.message.text.split(',') if c.strip()]
    user_data[chat_id]['chats'] = chats

    username = user_data[chat_id]['username']
    summary = f"🔎 Вы ввели:\nUsername: `{username}`\nЧаты:\n" + \
              '\n'.join(f"- `{c}`" for c in chats)
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm")],
        [InlineKeyboardButton("🔁 Изменить", callback_data="restart")],
    ]
    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "confirm":
        await query.edit_message_text(
            "⏳ Запрос отправлен \n"
            "Вы получите данные после выполнения задачи"
        )
        payload = {
            "username": user_data[chat_id]['username'],
            "chats": user_data[chat_id]['chats'],
        }
        return await add_request_to_queue(query, payload)

    elif query.data == "restart":
        return await restart(query, context)

    return await menu(update, context)


async def add_request_to_queue(query, payload):
    try:
        connection = await aio_pika.connect_robust(f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}/")
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(RABBITMQ_QUEUE_HUMAN_SCANNER, durable=True)
            message_body = json.dumps({"data": payload, "chat_id": query.message.chat_id}).encode("utf-8")

            message = aio_pika.Message(
                body=message_body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            )
            await channel.default_exchange.publish(
                message,
                routing_key=queue.name,
            )

    except Exception as e:
        logger.error(f"{LOGGER_PREFIX} - adding to queue error: {str(e)}")

    return MENU


if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start)
        ],
        states={
            MENU: [
                CallbackQueryHandler(handle_menu, pattern="^(human_scan|info)$")
            ],
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            CHATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_chats)],
            CONFIRM: [
                CallbackQueryHandler(handle_confirmation, pattern="^(confirm|restart)$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(restart, pattern="^restart$"),
        ],
    )

    app.add_handler(conv)
    app.run_polling()
