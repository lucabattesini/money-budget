from graph.state import AssistantState
from agents.orchestrator.run import run_orchestrator
from agents.query.run import run_query
from agents.recorder.run import run_recorder
from agents.secretary.run import run_secretary

def node_orchestrator(state: AssistantState):
    response = run_orchestrator(state["user_message"])
    return {"intent": response.type}

def node_recorder(state: AssistantState):
    response = run_recorder(state["user_message"])
    return {
        "extracted_items": response.items,
        "final_response": "Registro(s) processado(s) com sucesso!"
    }

def node_query(state: AssistantState):
    response = run_query(state["user_message"])
    return {"sql_query": response.sql_query}

def node_db_execute(state: AssistantState):
    fake_db_result = [{"total": 150}] 
    return {"db_results": fake_db_result}

def node_secretary(state: AssistantState):
    response = run_secretary(state["user_message"], str(state["db_results"]))
    return {"final_response": response.reply}

def node_off_topic(state: AssistantState):
    return {"final_response": "Desculpe, só consigo te ajudar com suas finanças."}
