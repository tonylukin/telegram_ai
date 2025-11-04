from fastapi import APIRouter, Request
from fastapi.params import Depends

from app.services.telegram.bot_health_checker import BotHealthChecker

router = APIRouter(prefix="/health")

@router.get("/bots-status")
async def check_bots_statuses(request: Request, bot_health_checker: BotHealthChecker = Depends()):
    all_roles = bool(request.query_params.get("all-roles", False))
    results = await bot_health_checker.check_bots_statuses(all_roles)
    return results
