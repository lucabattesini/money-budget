from sqlalchemy.orm import Session

from api.repositories.users_repo import get_user_by_whatsapp_phone
from config import FRONT_URL
from graph.graph import app


def process_whatsapp_message(db: Session, sender_number: str, message_text: str):
    user = get_user_by_whatsapp_phone(db, sender_number)

    if not user:
        return {
            "reply": f"Você ainda não tem uma conta, por favor, crie no link abaixo:\n{FRONT_URL}/#/login-google?phone={sender_number}"
        }

    initial_state = {"user_message": message_text, "user_id": user.id, "family_id": user.family_id}

    # The lookup above opened a transaction that keeps a pool connection until the request ends. The graph's nodes each
    # open their own session, so holding this one through the (slow) model calls would make every message need two
    # connections at once: with a small pool two messages at the same time wait for each other (TKT-107).
    db.rollback()

    result = app.invoke(initial_state)

    return {"reply": result.get("final_response", "")}
