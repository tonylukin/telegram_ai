from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

def get_user_id_from_update(update: Update):
    return update.effective_user.id if hasattr(update, 'effective_user') else update.message.from_user.id

def back_keyboard(user_id: int, t: callable):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(f"⬅️ {t(user_id, 'back')}", callback_data="back")]]
    )

def get_user_info_from_update(update: Update):
    user = update.effective_user
    name_parts = []
    if user.first_name:
        name_parts.append(user.first_name)
    if user.last_name:
        name_parts.append(user.last_name)
    if user.username:
        name_parts.append('@' + user.username)
    return {
        "user_id": user.id,
        "name": ' '.join(name_parts),
    }
