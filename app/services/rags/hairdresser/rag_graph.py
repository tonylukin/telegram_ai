import json
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from app.config import OPEN_AI_TEXT_MODEL, LEADS_FROM_CHANNEL_AI_PROMPT_CONDITION
from app.db.queries.tg_lead import get_tg_leads_by_messages
from app.db.session import Session
from app.dependencies import get_db
from .rag_seed_store import RAGSeedStore


# ------- STATE -------
class State(BaseModel):
    messages: list[str]
    positive: list | None = None
    negative: list | None = None
    existing_negative: list | None = None
    prompt: str | None = None
    output: str | None = None


# ------- COMPONENTS -------
store = RAGSeedStore()
# llm = ChatOpenAI(model="gpt-4o-mini")
llm = ChatOpenAI(model=OPEN_AI_TEXT_MODEL)

WORKFLOW_NAME = 'hairdresser'

prompt_tpl = PromptTemplate.from_template("""
Даны сообщения людей на разные темы.
Нужно выбрать сообщения ТОЛЬКО из списка сообщений, используя условие: "{condition}".

Список сообщений, из которых нужно выбрать, в формате JSON {{"text": "текст сообщения", "id": "айди сообщения", "name": "имя отправителя"}}:
[{messages}]

Список положительных примеров в формате JSON. Просто для формирования контекста и понимания, какие сообщения были выбраны удачно из другого списка, из этого списка нельзя выбирать:
{positive}

Отрицательные примеры в формате JSON, подобные сообщения нельзя выбирать:
{negative}

Верни первое сообщение из списка, которое удовлетворяет указанному условию в формате JSON с той же структурой {{"text", "id", "name"}}. 
Eсли такого сообщения нет, верни пустую строку.
""")


# ------- NODES -------
def retrieve_node(state: State):
    examples = store.query("\n\n".join([json.loads(m).get("text") for m in state.messages]), k=10)
    return {
        "positive": examples["positive"],
        "negative": examples["negative"],
    }

def fetch_existing(state: State):
    session = Session()
    messages = [json.loads(m).get('text') for m in state.messages]
    tg_leads = get_tg_leads_by_messages(session=session, messages=messages, workflow=WORKFLOW_NAME)
    existing_negative = [lead.message for lead in tg_leads]
    session.close()
    return {"existing_negative": existing_negative}


def prompt_node(state: State):
    filtered_messages = [m for m in state.messages if json.loads(m).get('text') not in state.existing_negative]
    msg = prompt_tpl.format(
        condition=LEADS_FROM_CHANNEL_AI_PROMPT_CONDITION,
        messages=','.join(filtered_messages),
        positive=json.dumps(state.positive, ensure_ascii=False),
        negative=json.dumps(state.negative, ensure_ascii=False),
    )

    return {"prompt": msg}


def llm_node(state: State):
    result = llm.invoke(state.prompt)
    return {"output": result.content.strip()}


# ------- GRAPH -------
graph = StateGraph(State)

graph.add_node("retrieve", retrieve_node)
graph.add_node("fetch_existing", fetch_existing)
graph.add_node("prompt", prompt_node)
graph.add_node("llm", llm_node)

graph.add_edge("retrieve", "fetch_existing")
graph.add_edge("fetch_existing", "prompt")
graph.add_edge("prompt", "llm")

graph.set_entry_point("retrieve")
graph.set_finish_point("llm")

rag_graph = graph.compile()
