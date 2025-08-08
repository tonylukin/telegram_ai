from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends, Header
from pydantic import BaseModel

from app.configs.logger import logger
from app.services.instagram_user_info_collector import InstagramUserInfoCollector
from app.services.user_info_collector import UserInfoCollector

router = APIRouter(prefix="/user-info", tags=["User Info"])

class UserInfoBody(BaseModel):
    username: str
    chats: Optional[list[str]] = None

@router.post("/collect")
async def user_info(body: UserInfoBody, x_language_code: str = Header(default="ru"), user_info_collector: UserInfoCollector = Depends()):
    try:
        result = await user_info_collector.get_user_info(username=body.username, channel_usernames=body.chats, lang=x_language_code)
        return {"status": "ok", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"User info collector error: {e}")
        raise HTTPException(status_code=500, detail='Please try again')

@router.post("/ig-collect")
async def ig_user_info(body: UserInfoBody, x_language_code: str = Header(default="ru"), instagram_user_info_collector: InstagramUserInfoCollector = Depends()):
    try:
        result = await instagram_user_info_collector.get_user_info(username=body.username, lang=x_language_code)
        return {"status": "ok", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Instagram user info collector error: {e}")
        raise HTTPException(status_code=500, detail='Please try again')