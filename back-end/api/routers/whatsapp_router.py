import os
from fastapi import APIRouter, Request, Response, status, Query
from fastapi.responses import PlainTextResponse
from api.controllers.whatsapp_controller import process_whatsapp_message
router = APIRouter(
    prefix="/webhook",
    tags=["whatsapp"]
)

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "my_secret_token_123")

@router.get("/")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    if hub_mode and hub_verify_token:
        if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
            print("WEBHOOK SUCCESSFULLY VERIFIED!")
            return PlainTextResponse(content=hub_challenge, status_code=200)
        else:
            return Response(status_code=status.HTTP_403_FORBIDDEN)
    
    return Response(status_code=status.HTTP_400_BAD_REQUEST)

@router.post("/")
async def receive_message(request: Request):
    try:
        body = await request.json()
        
        msg = body["entry"][0]["changes"][0]["value"]["messages"][0]
        result = process_whatsapp_message(msg["from"], msg["text"]["body"])
        print(f"AI RESPONSE TO {msg['from']}:", result["reply"])

        return {"status": "success", "reply": result["reply"]}

    except Exception as e:
        print("ERROR PROCESSING WEBHOOK:", e)
        return {"status": "error", "message": str(e)}
