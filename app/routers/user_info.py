import traceback
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel

from app.configs.logger import logger
from app.services.user_info_collector import UserInfoCollector

router = APIRouter(prefix="/user-info", tags=["User Info"])

class UserInfoBody(BaseModel):
    username: str
    chats: Optional[list[str]] = None

@router.post("/collect")
async def user_info(body: UserInfoBody, user_info_collector: UserInfoCollector = Depends()):
    try:
        result = await user_info_collector.get_user_info(username=body.username, channel_usernames=body.chats)
        return {"status": "ok", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"User info collector error: {e}", traceback.format_exc()) # todo check for traceback - do we need it?
        raise HTTPException(status_code=500, detail='Please try again')