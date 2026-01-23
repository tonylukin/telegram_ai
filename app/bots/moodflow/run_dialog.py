from sqlalchemy.ext.asyncio import AsyncSession
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.services.moodflow.mood_state import BotMood
from app.config import OPENAI_API_KEY
from app.services.moodflow.build_graph_with_store import build_graph_with_store
from app.services.moodflow.memory_store_pg import MemoryStorePG

# todo model names to config
llm = ChatOpenAI(
    model="gpt-5-nano",
    api_key=OPENAI_API_KEY
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
)


async def run_dialog_turn(user_id: int, user_text: str, session: AsyncSession, mood: BotMood) -> str:
    store = MemoryStorePG(session)

    await store.append_message(user_id, "user", user_text)

    graph = build_graph_with_store(store=store, llm=llm, embeddings=embeddings)
    result = await graph.ainvoke({"user_id": user_id, "user_text": user_text, "mood": mood})

    return result["assistant_text"]
