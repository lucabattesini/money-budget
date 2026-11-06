import json
import os

import requests


def whatsapp_configured() -> bool:
    """True once the WhatsApp keys are set. Until then the chatbot does not exist: nothing is read or answered."""
    return bool(os.getenv("WHATSAPP_TOKEN") and os.getenv("WHATSAPP_PHONE_ID"))


def send_whatsapp_message(to_number: str, message_body: str):
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_ID")

    if not token or not phone_id:
        print("WARNING: WHATSAPP_TOKEN or WHATSAPP_PHONE_ID not set in .env")
        print("Message not sent: WhatsApp is not configured")
        return None

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": message_body}}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print("Message sent successfully")
        return response.json()
    except requests.exceptions.HTTPError as err:
        print("HTTP Error when sending WhatsApp message:", err)
        print("Meta API Response:", response.text)
    except Exception as e:
        print("Error connecting to Meta API:", str(e))

    return None
