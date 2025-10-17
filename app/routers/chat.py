from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.queries import bot_comment, tg_user_invited
from app.dependencies import get_db
from app.schemas.BotCommentSchema import BotCommentSchema
from app.schemas.TgUserInvitedSchema import TgUserInvitedSchema
from app.services.telegram.assigned_channels_messenger import AssignedChannelsMessenger
from app.services.telegram.bullying_machine import BullyingMachine
from app.services.telegram.chat_messenger import ChatMessenger
from app.services.telegram.chat_search_exporter import ChatSearchExporter
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
    messages: Optional[list[str]] = None
    bot_roles: Optional[list[str]] = None

@router.post("/generate-messages")
async def generate_messages(body: GenerateMessagesBody, chat_messenger: ChatMessenger = Depends()):
    try:
        result = await chat_messenger.send_messages_to_chats_by_names(names=body.names, messages=body.messages, bot_roles=body.bot_roles)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-comments")
async def generate_comments(body: GenerateMessagesBody, assigned_channels_messenger: AssignedChannelsMessenger = Depends()):
    try:
        result = await assigned_channels_messenger.send_messages_to_assigned_channels(names=body.names, message=body.messages[0], bot_roles=body.bot_roles)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class InviteUsersBody(BaseModel):
    source_channels: Optional[list[str]] = None
    target_channels: Optional[list[str]] = None

@router.post("/invite-users")
async def invite_users(body: InviteUsersBody, user_inviter: UserInviter = Depends()):
    try:
        result = await user_inviter.invite_users_from_comments(source_channels=body.source_channels, target_channels=body.target_channels)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bot-comments", response_model=list[BotCommentSchema])
def get_users(limit: int = 50, offset: int = 0, session: Session = Depends(get_db)):
    bot_comments = bot_comment.find_all(session, limit=limit, offset=offset)
    return bot_comments

@router.get("/tg-users-invited", response_model=list[TgUserInvitedSchema])
def get_users(limit: int = 50, offset: int = 0, session: Session = Depends(get_db)):
    tg_users_invited = tg_user_invited.find_all(session, limit=limit, offset=offset)
    return tg_users_invited

class BullyingBody(BaseModel):
    username: str
    channel_names: list[str]

@router.post("/bullying")
async def bullying(body: BullyingBody, bullying_machine: BullyingMachine = Depends()):
    try:
        result = await bullying_machine.answer_to_messages(username=body.username, channel_usernames=body.channel_names)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat-search-export")
async def chat_search_export(chat_search_exporter: ChatSearchExporter = Depends()):
    try:
        result = await chat_search_exporter.export()
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
