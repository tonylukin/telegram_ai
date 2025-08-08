from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
import aio_pika
import json

from app.config import TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, RABBITMQ_QUEUE_HUMAN_SCANNER, \
    RABBITMQ_QUEUE_INSTAGRAM_HUMAN_SCANNER
from app.configs.logger import logger
from app.config import RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_HOST
from translations import translations

MENU, USERNAME, CHATS, CONFIRM = range(4)
IG_USERNAME = 'ig_username'
IG_CONFIRM = 'ig_confirm'
LOGGER_PREFIX = 'HumanScannerBot'
DEFAULT_LANGUAGE = 'ru'
user_data = {}
user_lang = {} #todo to DB

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = __get_user_id_from_update(update)
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
        [InlineKeyboardButton(f"✈️ {t(user_id, 'human_scan')}", callback_data="human_scan")],
        # [InlineKeyboardButton(f"📸 {t(user_id, 'ig_human_scan')}", callback_data="ig_human_scan")], todo uncomment
        [InlineKeyboardButton(f"ℹ️ {t(user_id, 'about')}", callback_data="info")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"), InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")]
    ]
    await message.reply_text(
        t(user_id, 'greeting'),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MENU


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = __get_user_id_from_update(update)

    if query.data == "human_scan":
        user_data[chat_id] = {}
        await query.message.reply_text(
            t(user_id, 'set_username'),
        )
        return USERNAME

    elif query.data == "ig_human_scan":
        user_data[chat_id] = {}
        await query.message.reply_text(
            t(user_id, 'ig_set_username'),
        )
        return IG_USERNAME

    elif query.data == "info":
        await query.message.reply_text(
            t(user_id, 'info'),
        )
        return await show_menu_again(query, context)


async def show_menu_again(query, context):
    user_id = query.from_user.id
    keyboard = [
        [InlineKeyboardButton(f"✈️ {t(user_id, 'human_scan')}", callback_data="human_scan")],
        # [InlineKeyboardButton(f"📸 {t(user_id, 'ig_human_scan')}", callback_data="ig_human_scan")], #todo uncomment
        [InlineKeyboardButton(f"ℹ️ {t(user_id, 'about')}", callback_data="info")],
    ]

    await query.message.reply_text(
        t(user_id, 'next'),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MENU

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang_code = query.data.split("_")[1]
    user_id = query.from_user.id
    user_lang[user_id] = lang_code

    return await menu(update, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await menu(update, context)

async def restart(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    return await menu(update_or_query, context)

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = __get_user_id_from_update(update)
    user_data[chat_id]['username'] = update.message.text

    await update.message.reply_text(
        t(user_id, 'enter_chats')
    )
    return CHATS

async def ig_get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data[chat_id]['username'] = update.message.text
    user_id = __get_user_id_from_update(update)

    keyboard = [
        [InlineKeyboardButton(f"✅ {t(user_id, 'confirm')}", callback_data="ig_confirm")],
        [InlineKeyboardButton(f"🔁 {t(user_id, 'start_over')}", callback_data="restart")],
    ]
    await update.message.reply_text(
        user_data[chat_id]['username'],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return IG_CONFIRM

async def get_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = __get_user_id_from_update(update)
    chats = [c.strip() for c in update.message.text.split(',') if c.strip()]
    user_data[chat_id]['chats'] = chats

    username = user_data[chat_id]['username']
    summary = f"🔎 {t(user_id, 'entered_chats').format(username=username)}" + \
              '\n'.join(f"- `{c}`" for c in chats)
    keyboard = [
        [InlineKeyboardButton(f"✅ {t(user_id, 'confirm')}", callback_data="confirm")],
        [InlineKeyboardButton(f"🔁 {t(user_id, 'start_over')}", callback_data="restart")],
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
    user_id = __get_user_id_from_update(update)

    if query.data == "confirm":
        chat_id = query.message.chat_id
        await query.edit_message_text(
            t(user_id, 'query_sent'),
        )
        payload = {
            "username": user_data[chat_id]['username'],
            "chats": user_data[chat_id]['chats'],
        }
        return await add_request_to_queue(RABBITMQ_QUEUE_HUMAN_SCANNER, query, payload)

    elif query.data == "ig_confirm":
        chat_id = query.message.chat_id
        await query.edit_message_text(
            t(user_id, 'query_sent'),
        )
        payload = {
            "username": user_data[chat_id]['username'],
        }
        return await add_request_to_queue(RABBITMQ_QUEUE_INSTAGRAM_HUMAN_SCANNER, query, payload)

    elif query.data == "restart":
        return await restart(query, context)

    return await menu(update, context)

def __get_user_id_from_update(update: Update):
    return update.effective_user.id if hasattr(update, 'effective_user') else update.message.from_user.id

async def add_request_to_queue(queue_name: str, query, payload):
    user_id = query.from_user.id
    lang_code = user_lang.get(user_id, DEFAULT_LANGUAGE)
    try:
        connection = await aio_pika.connect_robust(f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}/")
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(queue_name, durable=True)
            message_body = json.dumps({"data": payload, "chat_id": query.message.chat_id, "lang_code": lang_code}).encode("utf-8")

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

def t(user_id, key):
    lang = user_lang.get(user_id, DEFAULT_LANGUAGE)
    return translations.get(lang).get(key, key)


if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start)
        ],
        states={
            MENU: [
                CallbackQueryHandler(handle_menu, pattern="^(ig_human_scan|human_scan|info)$"),
                CallbackQueryHandler(set_language, pattern="^lang_")
            ],
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            CHATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_chats)],
            IG_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ig_get_username)],
            IG_CONFIRM: [CallbackQueryHandler(handle_confirmation, pattern="^(ig_confirm|restart)$")],
            CONFIRM: [CallbackQueryHandler(handle_confirmation, pattern="^(confirm|restart)$")],
        },
        fallbacks=[
            CallbackQueryHandler(restart, pattern="^restart$"),
        ],
    )
    app.add_handler(conv)
    app.run_polling()
