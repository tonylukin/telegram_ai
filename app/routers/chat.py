from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel

from app.services.telegram.assigned_channels_messenger import AssignedChannelsMessenger
from app.services.telegram.chat_messenger import ChatMessenger
from app.services.telegram.reaction_sender import ReactionSender
from app.services.telegram.user_inviter import UserInviter

router = APIRouter(prefix="/chat", tags=["Chat"])

class GenerateReactionsBody(BaseModel):
    query: Optional[str] = None
    names: Optional[list[str]] = None

@router.post("/generate-reactions")
async def generate_reactions(body: GenerateReactionsBody, reaction_sender: ReactionSender = Depends()):
    try:
        result = await reaction_sender.send_reactions(query=body.query, names=body.names)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GenerateMessagesBody(BaseModel):
    names: Optional[list[str]] = None
    message: Optional[str] = None

@router.post("/generate-messages")
async def generate_messages(body: GenerateMessagesBody, chat_messenger: ChatMessenger = Depends()):
    try:
        result = await chat_messenger.send_messages_to_chats_by_names(names=body.names, message=body.message)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-comments")
async def generate_comments(body: GenerateMessagesBody, assigned_channels_messenger: AssignedChannelsMessenger = Depends()):
    try:
        result = await assigned_channels_messenger.send_messages_to_assigned_channels(names=body.names, message=body.message)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/invite-users")
async def invite_users(user_inviter: UserInviter = Depends()):
    try:
        result = await user_inviter.invite_users_from_comments()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
