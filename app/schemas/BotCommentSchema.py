from pydantic import BaseModel
from datetime import datetime

from app.schemas.BotSchema import BotSchema

class BotCommentSchema(BaseModel):
    id: int
    comment: str
    channel: str
    created_at: datetime
    bot: BotSchema

    class Config:
        from_attributes = True