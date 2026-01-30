from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.services.moodflow.mood_state import BotMood
from app.config import OPENAI_API_KEY, OPEN_AI_TEXT_MODEL
from app.services.moodflow.build_graph_with_store import build_graph_with_store
from app.services.moodflow.memory_store_pg import MemoryStorePG

llm = ChatOpenAI(
    model=OPEN_AI_TEXT_MODEL,
    api_key=OPENAI_API_KEY
)

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
)


async def run_dialog_turn(user_id: int, user_text: str, store: MemoryStorePG, mood: BotMood, user_msg_id: int) -> str:

    await store.append_message(
        user_id,
        "user",
        user_text,
        tg_message_id=user_msg_id,
    )

    graph = build_graph_with_store(store=store, llm=llm, embeddings=embeddings)
    result = await graph.ainvoke({"user_id": user_id, "user_text": user_text, "mood": mood, "user_msg_id": user_msg_id})

    return result["assistant_text"]
