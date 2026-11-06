import os

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from api.controllers.whatsapp_controller import process_whatsapp_message
from api.services.whatsapp_service import send_whatsapp_message, whatsapp_configured
from db.connection import get_db

router = APIRouter(prefix="/webhook", tags=["whatsapp"])

VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")


@router.get("/")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode and hub_verify_token:
        if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
            print("WEBHOOK SUCCESSFULLY VERIFIED!")
            return PlainTextResponse(content=hub_challenge, status_code=200)
        else:
            return Response(status_code=status.HTTP_403_FORBIDDEN)

    return Response(status_code=status.HTTP_400_BAD_REQUEST)


@router.post("/")
async def receive_message(request: Request, db: Session = Depends(get_db)):
    # The webhook has no signature check yet (TKT-27), so on a public address anyone could post a message for any
    # phone number. Until WhatsApp is set up, nothing is accepted.
    if not whatsapp_configured():
        return JSONResponse({"status": "error", "message": "WhatsApp is not configured"}, status_code=503)
    try:
        body = await request.json()

        msg = body["entry"][0]["changes"][0]["value"]["messages"][0]
        result = process_whatsapp_message(db, msg["from"], msg["text"]["body"])
        send_whatsapp_message(msg["from"], result["reply"])

        return {"status": "success", "reply": result["reply"]}

    except Exception as e:
        print("ERROR PROCESSING WEBHOOK:", e)
        return {"status": "error", "message": str(e)}
