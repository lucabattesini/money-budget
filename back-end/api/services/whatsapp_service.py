import os
import requests
import json

def send_whatsapp_message(to_number: str, message_body: str):
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_ID")

    if not token or not phone_id:
        print("WARNING: WHATSAPP_TOKEN or WHATSAPP_PHONE_ID not set in .env")
        print(f"Message that would be sent to {to_number}: {message_body}")
        return None

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {
            "body": message_body
        }
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        print(f"Message sent successfully to {to_number}")
        return response.json()
    except requests.exceptions.HTTPError as err:
        print("HTTP Error when sending WhatsApp message:", err)
        print("Meta API Response:", response.text)
    except Exception as e:
        print("Error connecting to Meta API:", str(e))
        
    return None
