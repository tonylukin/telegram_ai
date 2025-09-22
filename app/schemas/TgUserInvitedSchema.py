from pydantic import BaseModel
from datetime import datetime

from app.schemas.BotSchema import BotSchema

class TgUserInvitedSchema(BaseModel):
    id: int
    tg_user_id: int
    channel: str
    tg_username: str | None
    channel_from: str | None
    created_at: datetime
    bot: BotSchema | None

    class Config:
        from_attributes = True