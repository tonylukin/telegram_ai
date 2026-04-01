from typing import Optional

from fastapi import APIRouter, HTTPException, Request
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
from app.services.telegram.chat_poster import ChatPoster
from app.services.telegram.chat_search_exporter import ChatSearchExporter
from app.services.telegram.user_inviter import UserInviter

router = APIRouter(prefix="/chat", tags=["Chat"])

class GenerateMessagesBody(BaseModel):
    names: Optional[list[str]] = None
    messages: Optional[list[str]] = None
    bot_roles: Optional[list[str]] = None
    max_channels_per_bot: Optional[int] = None
    bot_limit: Optional[int] = None
    csv_path: Optional[str] = None

@router.post("/generate-messages")
async def generate_messages(body: GenerateMessagesBody, chat_messenger: ChatMessenger = Depends()):
    try:
        result = await chat_messenger.send_messages_to_chats_by_names(
            names=body.names,
            messages=body.messages,
            bot_roles=body.bot_roles,
            max_channels_per_bot=body.max_channels_per_bot,
            bot_limit=body.bot_limit,
            csv_path=body.csv_path,
        )
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
async def chat_search_export(request: Request, chat_search_exporter: ChatSearchExporter = Depends()):
    try:
        data = await request.json()
        result = await chat_search_exporter.export(
            queries=data.get('queries'),
            output_filename=data.get('output_filename'),
            channel_min_count=data.get('channel_min_count'),
            channel_max_count=data.get('channel_max_count'),
        )
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/post-prompted-messages-to-channels")
async def post_prompted_messages_to_channels(request: Request, chat_poster: ChatPoster = Depends()):
    try:
        data = await request.json()
        result = await chat_poster.send_prompted_messages_to_chats_by_names(prompt=data.get('prompt'), chat_names=data.get('chat_names'))
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/post-simple-messages-to-channels")
async def post_simple_messages_to_channels(request: Request, chat_poster: ChatPoster = Depends()):
    try:
        data = await request.json()
        result = await chat_poster.send_simple_messages_to_chats_by_names(messages=data.get('messages'), chat_names=data.get('chat_names'), limit=data.get('limit', 1))
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
