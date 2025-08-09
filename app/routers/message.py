from fastapi.params import Depends
from fastapi import APIRouter, HTTPException
from fastapi import Request

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
