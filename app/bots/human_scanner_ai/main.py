from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)
import aio_pika
import json

from app.config import TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, RABBITMQ_QUEUE_HUMAN_SCANNER, \
    RABBITMQ_QUEUE_INSTAGRAM_HUMAN_SCANNER, RABBITMQ_QUEUE_TIKTOK_HUMAN_SCANNER
from app.configs.logger import logger
from app.config import RABBITMQ_USER, RABBITMQ_PASSWORD, RABBITMQ_HOST
from app.services.notification_sender import NotificationSender
from translations import translations
from app.bots.utils import get_user_id_from_update, back_keyboard, get_user_info_from_update

(TG_USERNAME, TG_CHATS, TG_CONFIRM,
 IG_USERNAME, IG_CONFIRM,
 TIKTOK_USERNAME, TIKTOK_CONFIRM,
 SET_FEEDBACK) = range(8)
GENERAL = 'general'
LOGGER_PREFIX = 'HumanScannerBot'
DEFAULT_LANGUAGE = 'ru'
user_data = {}
user_lang = {} #todo to DB
notification_sender = NotificationSender()

get_intro = lambda user_id: t(user_id, 'greeting')

def main_menu_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton(f"✈️ {t(user_id, 'human_scan')}", callback_data="human_scan")],
        [InlineKeyboardButton(f"📸 {t(user_id, 'ig_human_scan')}", callback_data="ig_human_scan")],
        [InlineKeyboardButton(f"🎵 {t(user_id, 'tiktok_human_scan')}", callback_data="tiktok_human_scan")],
        [InlineKeyboardButton(f"ℹ️ {t(user_id, 'about')}", callback_data="info"),
         InlineKeyboardButton(f"💬 {t(user_id, 'feedback')}", callback_data="feedback")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")]
    ]
    return InlineKeyboardMarkup(buttons)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id_from_update(update)
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

    await message.reply_text(
        get_intro(user_id),
        reply_markup=main_menu_keyboard(user_id)
    )
    return GENERAL


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('Start this ' + update.callback_query.data)
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = get_user_id_from_update(update)

    if query.data == "human_scan":
        user_data[chat_id] = {}
        await query.message.reply_text(
            t(user_id, 'set_username'),
            reply_markup=back_keyboard(user_id, t),
        )
        return TG_USERNAME

    elif query.data == "ig_human_scan":
        user_data[chat_id] = {}
        await query.message.reply_text(
            t(user_id, 'ig_set_username'),
            reply_markup=back_keyboard(user_id, t),
        )
        return IG_USERNAME

    elif query.data == "tiktok_human_scan":
        user_data[chat_id] = {}
        await query.message.reply_text(
            t(user_id, 'tiktok_set_username'),
            reply_markup=back_keyboard(user_id, t),
        )
        return TIKTOK_USERNAME

    elif query.data == "info":
        await query.edit_message_text(
            t(user_id, 'info'),
            reply_markup=back_keyboard(user_id, t),
        )

    elif query.data == "feedback":
        await query.edit_message_text(
            t(user_id, 'feedback_text'),
            reply_markup=back_keyboard(user_id, t),
        )
        return SET_FEEDBACK

    elif query.data == "back":
        await query.edit_message_text(
            text=get_intro(user_id),
            reply_markup=main_menu_keyboard(user_id),
        )

    print(f"{LOGGER_PREFIX} - handled callback: {query.data}")
    return GENERAL

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang_code = query.data.split("_")[1]
    user_id = query.from_user.id
    user_lang[user_id] = lang_code

    await query.edit_message_text(
        text=get_intro(user_id),
        reply_markup=main_menu_keyboard(user_id),
    )
    return GENERAL

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id_from_update(update)
    await update.message.reply_text(
        get_intro(user_id),
        reply_markup=main_menu_keyboard(user_id)
    )
    return GENERAL

async def restart(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    return await menu(update_or_query, context)

async def tg_get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('TG USERNAME')
    chat_id = update.effective_chat.id
    user_id = get_user_id_from_update(update)
    user_data[chat_id]['username'] = update.message.text

    await update.message.reply_text(
        t(user_id, 'enter_chats'),
        reply_markup=back_keyboard(user_id, t),
    )
    return TG_CHATS

async def ig_get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data[chat_id]['username'] = update.message.text
    user_id = get_user_id_from_update(update)

    keyboard = [
        [InlineKeyboardButton(f"✅ {t(user_id, 'confirm')}", callback_data="ig_confirm")],
        [InlineKeyboardButton(f"🔁 {t(user_id, 'start_over')}", callback_data="restart")],
    ]
    await update.message.reply_text(
        user_data[chat_id]['username'],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return IG_CONFIRM

async def tiktok_get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_data[chat_id]['username'] = update.message.text
    user_id = get_user_id_from_update(update)

    keyboard = [
        [InlineKeyboardButton(f"✅ {t(user_id, 'confirm')}", callback_data="tiktok_confirm")],
        [InlineKeyboardButton(f"🔁 {t(user_id, 'start_over')}", callback_data="restart")],
    ]
    await update.message.reply_text(
        user_data[chat_id]['username'],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TIKTOK_CONFIRM

async def set_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = get_user_id_from_update(update)
    user_info = get_user_info_from_update(update)
    text = f"{user_info.get('name')}:\n{update.message.text}"
    await notification_sender.send_notification_message(text)

    await update.message.reply_text(
        t(user_id, 'feedback_outro'),
        reply_markup=main_menu_keyboard(user_id)
    )
    return GENERAL

async def tg_get_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = get_user_id_from_update(update)
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
    return TG_CONFIRM

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = get_user_id_from_update(update)

    if query.data == "confirm":
        chat_id = query.message.chat_id
        await query.edit_message_text(
            t(user_id, 'query_sent'),
        )
        payload = {
            "username": user_data[chat_id]['username'],
            "chats": user_data[chat_id]['chats'],
        }
        return await add_request_to_queue(update, context, RABBITMQ_QUEUE_HUMAN_SCANNER, query, payload)

    elif query.data == "ig_confirm":
        chat_id = query.message.chat_id
        await query.edit_message_text(
            t(user_id, 'query_sent'),
        )
        payload = {
            "username": user_data[chat_id]['username'],
        }
        return await add_request_to_queue(update, context, RABBITMQ_QUEUE_INSTAGRAM_HUMAN_SCANNER, query, payload)

    elif query.data == "tiktok_confirm":
        chat_id = query.message.chat_id
        await query.edit_message_text(
            t(user_id, 'query_sent'),
        )
        payload = {
            "username": user_data[chat_id]['username'],
        }
        return await add_request_to_queue(update, context, RABBITMQ_QUEUE_TIKTOK_HUMAN_SCANNER, query, payload)

    elif query.data == "restart":
        return await restart(query, context)

    return await menu(update, context)


async def add_request_to_queue(update: Update, context: ContextTypes.DEFAULT_TYPE, queue_name: str, query, payload):
    user_id = query.from_user.id
    lang_code = user_lang.get(user_id, DEFAULT_LANGUAGE)
    try:
        connection = await aio_pika.connect_robust(f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}/")
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": f"{queue_name}.dlx",
                    "x-dead-letter-routing-key": queue_name,
                }
            )
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

    return await menu(update, context)

def t(user_id, key):
    lang = user_lang.get(user_id, DEFAULT_LANGUAGE)
    return translations.get(lang).get(key, key)


def main():
    app = ApplicationBuilder().token(TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start)
        ],
        states={
            GENERAL: [
                CallbackQueryHandler(set_language, pattern="^lang_"),
                CallbackQueryHandler(handle_callback), # , pattern="^(tiktok_human_scan|ig_human_scan|human_scan|info|feedback|back)$"),
            ],
            TG_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_get_username)],
            TG_CHATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_get_chats)],
            TG_CONFIRM: [CallbackQueryHandler(handle_confirmation, pattern="^(confirm|restart)$")],
            IG_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ig_get_username)],
            IG_CONFIRM: [CallbackQueryHandler(handle_confirmation, pattern="^(ig_confirm|restart)$")],
            TIKTOK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, tiktok_get_username)],
            TIKTOK_CONFIRM: [CallbackQueryHandler(handle_confirmation, pattern="^(tiktok_confirm|restart)$")],
            SET_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_feedback)],
        },
        fallbacks=[
            CallbackQueryHandler(restart, pattern="^restart|back$"),
        ],
    )
    app.add_handler(conv)

    app.run_polling()


if __name__ == '__main__':
    main()
