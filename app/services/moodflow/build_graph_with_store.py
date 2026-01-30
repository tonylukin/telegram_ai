from langgraph.graph import StateGraph, END

from app.services.moodflow.graph_state import GraphState
from app.services.moodflow.lang_graph_factory import build_nodes


def build_graph_with_store(
    *,
    store,
    llm,
    embeddings,
    history_limit: int = 20,
    memories_k: int = 10,
):
    load_context, rewrite_query, retrieve_memories, generate, extract_memories, store_results = build_nodes(
        store=store,
        llm=llm,
        embeddings=embeddings,
        history_limit=history_limit,
        memories_k=memories_k,
    )

    g = StateGraph(GraphState)

    g.add_node("load_context", load_context)
    g.add_node("rewrite_query", rewrite_query)
    g.add_node("retrieve_memories", retrieve_memories)
    g.add_node("generate", generate)
    g.add_node("extract_memories", extract_memories)
    g.add_node("store_results", store_results)

    g.set_entry_point("load_context")
    g.add_edge("load_context", "rewrite_query")
    g.add_edge("rewrite_query", "retrieve_memories")
    g.add_edge("retrieve_memories", "generate")
    g.add_edge("generate", "extract_memories")
    g.add_edge("extract_memories", "store_results")
    g.add_edge("store_results", END)

    return g.compile()
