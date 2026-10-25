from langgraph.graph import StateGraph, END
from graph.state import AssistantState
from graph.nodes import node_agent, node_tools, node_give_up

# Model turns allowed per message (each turn may call several tools at once)
MAX_STEPS = 4

workflow = StateGraph(AssistantState)

workflow.add_node("agent", node_agent)
workflow.add_node("tools", node_tools)
workflow.add_node("give_up", node_give_up)

def route_after_agent(state: AssistantState):
    if state.get("final_response"):
        return END
    if state["steps"] >= MAX_STEPS:
        return "give_up"
    return "tools"

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "tools": "tools",
        "give_up": "give_up",
        END: END
    }
)

workflow.add_edge("tools", "agent")
workflow.add_edge("give_up", END)

app = workflow.compile()
