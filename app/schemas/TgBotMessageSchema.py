from pydantic import BaseModel
from datetime import datetime

from app.schemas.BotSchema import BotSchema


class TgBotMessageSchema(BaseModel):
    id: int
    sender_name: str
    text: str
    reply_text: str
    created_at: datetime
    bot: BotSchema

    class Config:
        from_attributes = True
