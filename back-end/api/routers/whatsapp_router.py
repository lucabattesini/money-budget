import os
from fastapi import APIRouter, Request, Response, status, Query
from fastapi.responses import PlainTextResponse

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
        print("NEW MESSAGE RECEIVED:", body)
    except Exception as e:
        print("ERROR PROCESSING WEBHOOK:", e)
        
    return Response(status_code=status.HTTP_200_OK)
