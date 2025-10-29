from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.config import TELEGRAM_FUTURE_ADS_AI_BOT_TOKEN, TELEGRAM_FUTURE_ADS_NOTIFICATIONS_CHAT_ID
from app.services.notification_sender import NotificationSender
from translations import translations

DEFAULT_LANGUAGE = 'ru'
user_lang = {}
notification_sender = NotificationSender()

get_intro = lambda user_id: t(user_id, 'intro')
PAGES = {
    'auto_reply',
    'reactions',
    'comments',
    'followers',
    'automation',
    'bots',
    'mailing',
    'dm',
    'feedback',
}
waiting_for_feedback = set()  # user_ids awaiting response

def main_menu_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton(f"🤖 {t(user_id, 'answering_machine')}", callback_data="auto_reply"),
         InlineKeyboardButton(f"🔥 {t(user_id, 'reactions_btn')}", callback_data="reactions")],
        [InlineKeyboardButton(f"💬 {t(user_id, 'comments_btn')}", callback_data="comments"),
         InlineKeyboardButton(f"🚀 {t(user_id, 'subscribers_btn')}", callback_data="followers")],
        [InlineKeyboardButton(f"📢 {t(user_id, 'automation_btn')}", callback_data="automation"),
         InlineKeyboardButton(f"🛠️ {t(user_id, 'bot_creation')}", callback_data="bots")],
        [InlineKeyboardButton(f"📨 {t(user_id, 'mailing_btn')}", callback_data="mailing"),
         InlineKeyboardButton(f"💼 {t(user_id, 'dm_btn')}", callback_data="dm")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(f"📞 {t(user_id, 'feedback_btn')}", callback_data="feedback")],
    ]
    return InlineKeyboardMarkup(buttons)


def back_keyboard(user_id):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"⬅️ {t(user_id, 'back')}", callback_data="back")]]
    )

# todo move it to decorator
def __get_user_id_from_update(update: Update):
    return update.effective_user.id if hasattr(update, 'effective_user') else update.message.from_user.id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = __get_user_id_from_update(update)

    await update.message.reply_text(
        get_intro(user_id),
        reply_markup=main_menu_keyboard(user_id),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    if data == "back":
        await query.edit_message_text(
            text=get_intro(user_id),
            reply_markup=main_menu_keyboard(user_id),
        )

    elif data == "feedback":
        # show feedback text and wait for user message
        waiting_for_feedback.add(user_id)
        await query.edit_message_text(
            text=t(user_id, 'feedback') + f"\n\n✉️ {t(user_id, 'feedback_2')}",
            parse_mode="Markdown",
            reply_markup=back_keyboard(user_id),
        )

    elif data in PAGES:
        await query.edit_message_text(
            text=t(user_id, data),
            parse_mode="Markdown",
            reply_markup=back_keyboard(user_id),
        )
    else:
        await query.answer("Unknown callback data.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages from users (for feedback)."""
    user_id = update.message.from_user.id
    if user_id in waiting_for_feedback:
        text = update.message.text.strip()
        user_info = f"{update.message.from_user.first_name or ''} {update.message.from_user.last_name or ''}".strip()
        username = f"@{update.message.from_user.username}" if update.message.from_user.username else "(no username)"
        final_text = f"📬 Feedback from {user_info} {username}:\n\n{text}"

        result = await notification_sender.send_notification_message(final_text, TELEGRAM_FUTURE_ADS_NOTIFICATIONS_CHAT_ID)

        if result:
            await update.message.reply_text(
                f"✅ {t(user_id, 'feedback_received')}",
                reply_markup=main_menu_keyboard(user_id),
            )
        waiting_for_feedback.remove(user_id)
    else:
        # ignore random messages outside feedback
        await update.message.reply_text(get_intro(user_id), reply_markup=main_menu_keyboard(user_id))


def t(user_id, key):
    lang = user_lang.get(user_id, DEFAULT_LANGUAGE)
    return translations.get(lang).get(key, key)

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang_code = query.data.split("_")[1]
    user_id = query.from_user.id
    user_lang[user_id] = lang_code

    return await query.edit_message_text(
        text=get_intro(user_id),
        reply_markup=main_menu_keyboard(user_id),
    )

def main():
    app = ApplicationBuilder().token(TELEGRAM_FUTURE_ADS_AI_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()


if __name__ == "__main__":
    main()
