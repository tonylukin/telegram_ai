from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, MessageHandler, ContextTypes, filters
)

from app.services.moodflow.mood_state import get_state, update_mood, BotMood
from app.bots.moodflow.run_dialog import run_dialog_turn
from app.config import DATABASE_URL_ASYNC
from app.config import TELEGRAM_MOODFLOW_BOT_TOKEN


# from langchain_community.embeddings import SentenceTransformerEmbeddings

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

    # --- Load Vector DB ---
    # embeddings = HuggingFaceEmbeddings(
    #     model_name="sentence-transformers/all-MiniLM-L6-v2"
    # )
    #
    # db = Chroma(
    #     persist_directory="./chroma_db",
    #     embedding_function=embeddings
    # )
    #
    # retriever = db.as_retriever(search_kwargs={"k": 3})
    #
    # # --- LLM ---
    # llm = get_open_ai_client()

    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_text = update.message.text
        user_id = update.message.from_user.id
        state = get_state(user_id)
        mood, palette = update_mood(state, user_text)
        mood = BotMood.RUDE # todo remove

        async with AsyncSessionLocal() as session:
            try:
                response = await run_dialog_turn(user_id, user_text, session, mood)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        await update.message.reply_text(response)

    async def on_shutdown(app):
        # This cleanly closes the connection pool
        await engine.dispose()

    # --- App ---
    app = ApplicationBuilder().token(TELEGRAM_MOODFLOW_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.post_shutdown = on_shutdown

    print('Starting bot...')
    app.run_polling()

if __name__ == '__main__':
    main()
