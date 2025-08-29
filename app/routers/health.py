from fastapi import APIRouter
from fastapi.params import Depends

from app.services.telegram.bot_health_checker import BotHealthChecker

router = APIRouter(prefix="/health")

@router.get("/bots-status")
async def check_bots_statuses(bot_health_checker: BotHealthChecker = Depends()):
    results = await bot_health_checker.check_bots_statuses()
    return results
