from pydantic import BaseModel
from datetime import datetime

class TgUserCommentSchema(BaseModel):
    id: int
    comment: str | None
    channel: str | None
    created_at: datetime

    class Config:
        from_attributes = True
