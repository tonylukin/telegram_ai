from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.params import Depends

from app.services.telegram.reaction_sender import ReactionSender
from pydantic import BaseModel


router = APIRouter(prefix="/reactions", tags=["Reactions"])

class GenerateReactionsBody(BaseModel):
    query: Optional[str] = None
    chat_names: Optional[list[str]] = None

@router.post("/generate-reactions")
async def generate_reactions(body: GenerateReactionsBody, reaction_sender: ReactionSender = Depends()):
    try:
        result = await reaction_sender.send_reactions(query=body.query, chat_names=body.chat_names)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/react-on-user-messages")
async def react_on_user_messages(request: Request, reaction_sender: ReactionSender = Depends()):
    try:
        data = await request.json()
        result = await reaction_sender.send_reactions(reaction=data.get('reaction', '❤️'), chat_names=data.get('chat_names'), usernames=data.get('usernames'))
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
