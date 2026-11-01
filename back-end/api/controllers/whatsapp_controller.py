import os
from sqlalchemy.orm import Session
from api.repositories.users_repo import get_user_by_whatsapp_phone
from graph.graph import app

FRONT_URL = os.getenv("FRONT_URL", "http://localhost:5173")

def process_whatsapp_message(db: Session, sender_number: str, message_text: str):
    user = get_user_by_whatsapp_phone(db, sender_number)
    
    if not user:
        return {
            "reply": f"Você ainda não tem uma conta, por favor, crie no link abaixo:\n{FRONT_URL}/#/login-google?phone={sender_number}"
        }
    
    initial_state = {
        "user_message": message_text,
        "user_id": user.id
    }
    
    result = app.invoke(initial_state)
    
    return {"reply": result.get("final_response", "")}
