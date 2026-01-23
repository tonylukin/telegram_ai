from typing import TypedDict, Any, List, Dict

from app.services.moodflow.mood_state import BotMood


class GraphState(TypedDict, total=False):
    user_id: int
    user_text: str
    mood: BotMood

    profile: Dict[str, Any]
    short_history: List[Dict[str, str]]

    rewritten_query: str
    retrieved_memories: List[Dict[str, Any]]

    assistant_text: str

    new_memories: List[Dict[str, Any]]
    profile_patch: Dict[str, Any]
