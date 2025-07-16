from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
import aiohttp
import aio_pika
import json

from app.config import TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, APP_HOST, RABBITMQ_QUEUE_HUMAN_SCANNER, API_TOKEN
from app.configs.logger import logger
from app.config import ENV, RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_HOST

USERNAME, CHATS, CONFIRM = range(3)
LOGGER_PREFIX = 'HumanScannerBot'
user_data = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data[chat_id] = {}
    intro_text = (
        "👋 Привет! Этот бот дает описание человека на основе его активности в указанных каналах.\n"
        "У бота есть ограничения, поэтому будет использована активность за последнее время.\n"
        "Введите username (@ivan), если есть, либо полное имя аккаунта (Иван Иванов):"
    )
    await update.message.reply_text(intro_text)
    return USERNAME


async def restart(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    """Вызывается при 'Начать сначала'."""
    if isinstance(update_or_query, Update):  # /start
        chat_id = update_or_query.effective_chat.id
    else:  # callback_query
        query = update_or_query
        await query.answer()
        chat_id = query.message.chat_id
        await query.message.reply_text("🔄 Начинаем сначала. Кого ищем?")

    user_data[chat_id] = {}
    return USERNAME


async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data[chat_id]['username'] = update.message.text

    await update.message.reply_text(
        "Теперь введите список чатов, где у юзера есть активность (через запятую: @chat1, https://t.me/chat2, t.me/+инвайт).\n"
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
        return await send_request_with_retry(query, payload)

    elif query.data == "restart":
        return await restart(query, context)

    return ConversationHandler.END


async def retry_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    payload = {
        "username": user_data[chat_id]['username'],
        "chats": user_data[chat_id]['chats'],
    }

    await query.edit_message_text("⏳ Повторяю запрос...")
    return await send_request_with_retry(query, payload)


async def send_request_with_retry(query, payload):
    # if ENV == 'prod': #todo uncomment
    if True:
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

        return ConversationHandler.END

    ####### BELOW FOR DEV PURPOSES #######
    try:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{APP_HOST}/user-info/collect", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    desc = result["result"].get("description", "Нет описания.")
                    keyboard = [
                        [InlineKeyboardButton("🔄 Начать сначала", callback_data="restart")],
                    ]
                    await query.message.reply_text(
                        f"📄 Результат:\n\n{desc or 'Активность в чатах не обнаружена'}",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    await send_error_with_retry(query, f"⚠️ Ошибка сервера: {resp.status} {await resp.text()}")
    except Exception as e:
        await send_error_with_retry(query, f"❌ Ошибка при запросе:\n{str(e)}")

    return CONFIRM


async def send_error_with_retry(query, error_text):
    keyboard = [
        [InlineKeyboardButton("🔄 Повторить", callback_data="retry")],
        [InlineKeyboardButton("🚫 Начать сначала", callback_data="restart")],
    ]
    await query.message.reply_text(
        error_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚫 Операция отменена.")
    return ConversationHandler.END


if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start)
        ],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            CHATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_chats)],
            CONFIRM: [
                CallbackQueryHandler(handle_confirmation, pattern="^(confirm|restart)$"),
                CallbackQueryHandler(retry_request, pattern="^retry$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    app.add_handler(conv)
    app.run_polling()
