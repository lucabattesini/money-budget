from datetime import datetime
from graph.state import AssistantState
from agents.orchestrator.run import run_orchestrator
from agents.query.run import run_query
from agents.recorder.run import run_recorder
from agents.secretary.run import run_secretary
from api.repositories.transactions_repo import execute_agent_query, create_transaction
from api.repositories.categories_repo import get_category_by_name
from schemas.tables_schemas import Transaction

def node_orchestrator(state: AssistantState):
    response = run_orchestrator(state["user_message"])
    return {"intent": response.type}

def node_recorder(state: AssistantState):
    response = run_recorder(state["user_message"])
    
    for item in response.items:
        if item.amount is not None:
            cat_obj = get_category_by_name(item.Category)
            if not cat_obj:
                cat_obj = get_category_by_name("Outros")
            
            category_id_str = str(cat_obj.id) if cat_obj else item.Category

            t = Transaction(
                label="Registro via Assistente",
                value=int(item.amount * 100),
                category=category_id_str,
                date=datetime.now()
            )
            create_transaction(t, state["user_id"])
            
    return {
        "extracted_items": response.items,
        "final_response": "Registro(s) processado(s) com sucesso!"
    }

def node_query(state: AssistantState):
    response = run_query(state["user_message"])
    return {"sql_query": response.sql_query}

def node_db_execute(state: AssistantState):
    db_results = execute_agent_query(state["sql_query"], state["user_id"])
    return {"db_results": db_results}

def node_secretary(state: AssistantState):
    response = run_secretary(state["user_message"], str(state["db_results"]))
    return {"final_response": response.reply}

def node_off_topic(state: AssistantState):
    return {"final_response": "Desculpe, só consigo te ajudar com suas finanças."}
