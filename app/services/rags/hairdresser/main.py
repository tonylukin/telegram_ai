from .rag_graph import rag_graph, State

def run_workflow(messages: list[str]) -> dict:
    result = rag_graph.invoke(State(messages=messages))

    return result
