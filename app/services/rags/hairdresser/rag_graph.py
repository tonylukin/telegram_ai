from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from app.config import OPEN_AI_TEXT_MODEL, LEADS_FROM_CHANNEL_AI_PROMPT_CONDITION
from .rag_seed_store import RAGSeedStore


# ------- STATE -------
class State(BaseModel):
    messages: list[str]
    positive: list | None = None
    negative: list | None = None
    prompt: str | None = None
    output: str | None = None


# ------- COMPONENTS -------
store = RAGSeedStore()
# llm = ChatOpenAI(model="gpt-4o-mini")
llm = ChatOpenAI(model=OPEN_AI_TEXT_MODEL)
SEPARATOR = "<br>"

prompt_tpl = PromptTemplate.from_template("""
Даны сообщения людей на разные темы.
Нужно выбрать сообщения ТОЛЬКО из списка сообщений, используя условие: "{condition}".

Список сообщений, сообщения разделены символом '{separator}':
{messages}
**конец списка сообщений**

Список положительных примеров (разделены символом '{separator}'), из них НЕ нужно выбирать сообщения:
{positive}
**конец списка положительных примеров**

Отрицательные примеры (разделены символом '{separator}'):
{negative}
**конец списка отрицательных примеров**

Верни первое сообщение, которое является "положительным", не изменяя исходный текст сообщения; если такого сообщения нет, верни пустую строку.
""")


# ------- NODES -------
def retrieve_node(state: State):
    examples = store.query("\n\n".join(state.messages), k=10)
    return {
        "positive": examples["positive"],
        "negative": examples["negative"],
    }


def prompt_node(state: State):
    msg = prompt_tpl.format(
        condition=LEADS_FROM_CHANNEL_AI_PROMPT_CONDITION,
        messages=f"\n{SEPARATOR}\n".join(state.messages),
        positive=f"\n{SEPARATOR}\n".join(state.positive),
        negative=f"\n{SEPARATOR}\n".join(state.negative),
        separator=SEPARATOR,
    )
    return {"prompt": msg}


def llm_node(state: State):
    result = llm.invoke(state.prompt)
    return {"output": result.content.strip()}


# ------- GRAPH -------
graph = StateGraph(State)

graph.add_node("retrieve", retrieve_node)
graph.add_node("prompt", prompt_node)
graph.add_node("llm", llm_node)

graph.add_edge("retrieve", "prompt")
graph.add_edge("prompt", "llm")

graph.set_entry_point("retrieve")
graph.set_finish_point("llm")

rag_graph = graph.compile()
