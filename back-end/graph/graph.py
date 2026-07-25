from langgraph.graph import StateGraph, END
from graph.state import AssistantState
from graph.nodes import (
    node_orchestrator, node_recorder, node_query, 
    node_db_execute, node_secretary, node_off_topic
)

workflow = StateGraph(AssistantState)

workflow.add_node("orchestrator", node_orchestrator)
workflow.add_node("recorder", node_recorder)
workflow.add_node("query", node_query)
workflow.add_node("db_execute", node_db_execute)
workflow.add_node("secretary", node_secretary)
workflow.add_node("off_topic", node_off_topic)

def route_intent(state: AssistantState):
    intent = state.get("intent")
    if intent == "registry":
        return "recorder"
    elif intent == "check":
        return "query"
    return "off_topic"

workflow.set_entry_point("orchestrator")

workflow.add_conditional_edges(
    "orchestrator",
    route_intent,
    {
        "recorder": "recorder",
        "query": "query",
        "off_topic": "off_topic"
    }
)

workflow.add_edge("recorder", END)
workflow.add_edge("off_topic", END)
workflow.add_edge("query", "db_execute")
workflow.add_edge("db_execute", "secretary")
workflow.add_edge("secretary", END)

app = workflow.compile()
