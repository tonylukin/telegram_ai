from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from app.services.moodflow.extracted_memory import parse_extract_payload
from app.services.moodflow.graph_state import GraphState
from app.services.moodflow.memory_store_pg import MemoryStorePG
from app.services.moodflow.mood_state import BotMood, mood_to_prompt


def build_nodes(
    *,
    store: MemoryStorePG,
    llm: ChatOpenAI,
    embeddings: OpenAIEmbeddings,
    history_limit: int = 20,
    memories_k: int = 10,
):
    async def load_context(state: GraphState) -> GraphState:
        user_id = state["user_id"]
        state["profile"] = await store.get_profile(user_id)
        state["short_history"] = await store.get_recent_history(user_id, limit=history_limit)
        return state

    async def rewrite_query(state: GraphState) -> GraphState:
        prompt = [
            {
                "role": "system",
                "content": (
                    "Rewrite the user's message into a short semantic search query (5-12 words). "
                    "Remove fluff, keep key entities and intent. Return only the query."
                ),
            },
            {"role": "user", "content": state["user_text"]},
        ]
        r = await llm.ainvoke(prompt)
        q = (getattr(r, "content", "") or "").strip()
        state["rewritten_query"] = q or state["user_text"]
        return state

    async def retrieve_memories(state: GraphState) -> GraphState:
        q = state.get("rewritten_query") or state["user_text"]
        q_emb = await embeddings.aembed_query(q)

        mems = await store.search_memories(
            user_id=state["user_id"],
            query_embedding=q_emb,
            k=memories_k,
            types=["preference", "fact", "project", "episode"],
        )
        state["retrieved_memories"] = [
            {"type": m.type, "text": m.text, "importance": m.importance, "ts": m.ts} for m in mems
        ]
        return state

    async def _compose_messages(state: GraphState) -> List[Dict[str, str]]:
        profile = state.get("profile", {}) or {}
        memories = state.get("retrieved_memories", []) or []
        short_history = state.get("short_history", []) or []
        mood = mood_to_prompt(state.get("mood", BotMood.NEUTRAL))
        profile['mood'] = mood
        await store.patch_profile(user_id=state["user_id"], patch={'mood': mood})
        # print('cur mood:', mood)

        mem_block = "\n".join(
            f"- ({m['type']}, imp={m['importance']:.2f}) {m['text']}" for m in memories
        ) or "—"

        system = (
            "You are a Russian-speaking Telegram bot. Be highly personalized.\n"
            f"You have a mood, so your answers must strictly respect it: {mood} \n"
            "Use the user's profile, short chat history, and retrieved long-term memory.\n"
            "Do not invent user facts. If something is unknown, ask a clarifying question.\n"
            "Keep responses chatty and natural for Telegram. \n"
        )

        msgs: List[Dict[str, str]] = [{"role": "system", "content": system}]
        msgs.append({"role": "system", "content": f"User profile (JSON): {json.dumps(profile, ensure_ascii=False)}"})
        msgs.append({"role": "system", "content": f"Retrieved memory (RAG):\n{mem_block}"})

        for h in short_history[-history_limit:]:
            role = "user" if h["role"] == "user" else "assistant"
            msgs.append({"role": role, "content": h["text"]})

        # msgs.append({"role": "user", "content": state["user_text"]}) # last text is already in history
        return msgs

    async def generate(state: GraphState) -> GraphState:
        msgs = await _compose_messages(state)
        print('composed messages', msgs)
        r = await llm.ainvoke(msgs)
        state["assistant_text"] = (getattr(r, "content", "") or "").strip()
        return state

    async def extract_memories(state: GraphState) -> GraphState:
        extraction_prompt = [
            {
                "role": "system",
                "content": (
                    "Extract new long-term user memories that will matter later.\n"
                    "Only save stable preferences, durable facts, ongoing projects, or useful episode summaries.\n"
                    "Do not save one-off details, secrets, or sensitive personal data.\n"
                    "Return STRICT JSON with keys: memories (list) and profile_patch (object).\n"
                    "Each memory item: {\"type\": \"preference|fact|project|episode\", \"text\": \"...\", \"importance\": 0..1}\n"
                    "Return only JSON, no prose."
                ),
            },
            {
                "role": "user",
                "content": f"User: {state['user_text']}\nAssistant: {state['assistant_text']}",
            },
        ]

        r = await llm.ainvoke(extraction_prompt)
        raw = (getattr(r, "content", "") or "").strip()
        payload = parse_extract_payload(raw)

        state["new_memories"] = [m.model_dump() for m in payload.memories]
        state["profile_patch"] = payload.profile_patch
        return state

    async def store_results(state: GraphState) -> GraphState:
        user_id = state["user_id"]

        # todo we store tg_message_id from user message, but not from bot response -> when response sent in tg, we will update it to bot message id.
        #  Maybe we should have additional column to store user message id to have relation between user and bot messages?
        await store.append_message(user_id, "assistant", state["assistant_text"], tg_message_id=state["user_msg_id"])

        patch = state.get("profile_patch") or {}
        if patch:
            await store.patch_profile(user_id, patch)

        mems = state.get("new_memories") or []
        if mems:
            docs = []
            for m in mems:
                t = m.get("type")
                txt = (m.get("text") or "").strip()
                imp = float(m.get("importance", 0.5))
                if not t or not txt:
                    continue
                e = await embeddings.aembed_query(txt)
                docs.append((t, txt, e, imp))
            if docs:
                await store.upsert_memories(user_id=user_id, docs=docs, dedup=True)

        return state

    return load_context, rewrite_query, retrieve_memories, generate, extract_memories, store_results
