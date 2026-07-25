from api.repositories.users_repo import get_user_by_whatsapp_phone
from graph.graph import app

def process_whatsapp_message(sender_number: str, message_text: str):
    user = get_user_by_whatsapp_phone(sender_number)
    
    if not user:
        return {
            "reply": "Você ainda não tem uma conta, por favor, crie no link abaixo:\nhttps://seusite.com/signup"
        }
    
    initial_state = {
        "user_message": message_text,
        "user_id": user.id
    }
    
    result = app.invoke(initial_state)
    
    return {"reply": result.get("final_response", "")}
