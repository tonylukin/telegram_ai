from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from telegram import Update, ReactionTypeEmoji, ReactionTypeCustomEmoji
from telegram.ext import (
    ApplicationBuilder, MessageHandler, ContextTypes, filters, MessageReactionHandler
)
from app.services.moodflow.memory_store_pg import MemoryStorePG
from app.services.moodflow.mood_state import get_state, update_mood, BotMood
from app.bots.moodflow.run_dialog import run_dialog_turn, embeddings
from app.config import DATABASE_URL_ASYNC
from app.config import TELEGRAM_MOODFLOW_BOT_TOKEN
from app.services.telegram.reactions import Polarity, reaction_polarity


def feedback_to_preference_text(polarity: Polarity, bot_text: str) -> str:
    bot_text = bot_text.strip()
    if len(bot_text) > 400:
        bot_text = bot_text[:400] + "…"
    if polarity == Polarity.POSITIVE:
        return f"User reacted positively to this assistant message: {bot_text}"
    if polarity == Polarity.NEGATIVE:
        return f"User reacted negatively to this assistant message: {bot_text}"
    return ""


def main():
    engine = create_async_engine(
        DATABASE_URL_ASYNC,
        echo=False,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
        mr = update.message_reaction
        if mr is None:
            return

        user_id = mr.user.id if mr.user else None
        if user_id is None:
            return

        chat_id = mr.chat.id
        tg_message_id = mr.message_id

        new_reactions = mr.new_reaction or []

        async with AsyncSessionLocal() as session:
            store = MemoryStorePG(session)
            try:
                for r in new_reactions:
                    reaction_value = "unknown"
                    polarity: Polarity = Polarity.NEUTRAL

                    if isinstance(r, ReactionTypeEmoji):
                        reaction_value = r.emoji
                        polarity = reaction_polarity(r.emoji)
                    elif isinstance(r, ReactionTypeCustomEmoji):
                        reaction_value = r.custom_emoji_id
                        polarity = Polarity.NEUTRAL

                    await store.add_reaction(
                        user_id=user_id,
                        chat_id=chat_id,
                        tg_message_id=tg_message_id,
                        reaction_value=reaction_value,
                    )

                    if polarity in (Polarity.POSITIVE, Polarity.NEGATIVE):
                        bot_text = await store.get_message_text_by_chat_msg(
                            user_id=user_id,
                            tg_message_id=tg_message_id,
                        )
                        if bot_text:
                            pref_text = feedback_to_preference_text(polarity, bot_text)
                            if pref_text:
                                emb = await embeddings.aembed_query(pref_text)
                                await store.upsert_memories(
                                    user_id=user_id,
                                    docs=[("preference", pref_text, emb, 0.8 if polarity == Polarity.NEGATIVE else 0.7)],
                                    dedup=True,
                                )

                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        user_id = update.message.from_user.id
        state = get_state(user_id)
        mood, palette = update_mood(state, user_text)
        user_msg_id = update.message.message_id

        async with AsyncSessionLocal() as session:
            store = MemoryStorePG(session)
            try:
                response = await run_dialog_turn(user_id, user_text, store, mood, user_msg_id)
                bot_response = await update.message.reply_text(response)
                await store.patch_chat_message(user_id=user_id, tg_message_id=user_msg_id, role='assistant', set_values={
                    'tg_message_id': bot_response.message_id
                })

                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def on_shutdown(app):
        # This cleanly closes the connection pool
        await engine.dispose()

    # --- App ---
    app = ApplicationBuilder().token(TELEGRAM_MOODFLOW_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageReactionHandler(handle_reaction))
    app.post_shutdown = on_shutdown
    print('Starting bot...')
    app.run_polling(allowed_updates=["message", "message_reaction", "message_reaction_count"])

if __name__ == '__main__':
    main()
