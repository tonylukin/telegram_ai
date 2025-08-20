from fastapi.params import Depends
from fastapi import APIRouter, HTTPException
from fastapi import Request
from sqlalchemy.orm import Session

from app.db.queries.tg_bot_message import find_all
from app.dependencies import get_db
from app.schemas.TgBotMessageSchema import TgBotMessageSchema
from app.services.telegram.message_receiver import MessageReceiver

router = APIRouter(prefix="/message", tags=["Message"])

@router.post("/reply_to_all_messages")
async def reply_to_all_messages(request: Request, message_receiver: MessageReceiver = Depends()):
    try:
        data = await request.json()
        result = await message_receiver.check_and_reply(promoting_channel=data.get('promoting_channel'), promoting_channel_to_invite=data.get('promoting_channel_to_invite'))

        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tg-bot-messages", response_model=list[TgBotMessageSchema])
def get_tg_bot_messages(limit: int = 50, offset: int = 0, session: Session = Depends(get_db)):
    tg_bot_messages = find_all(session, limit=limit, offset=offset)
    return tg_bot_messages
