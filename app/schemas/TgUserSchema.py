from pydantic import BaseModel
from datetime import datetime

from app.schemas.TgUserCommentSchema import TgUserCommentSchema


class TgUserSchema(BaseModel):
    id: int
    tg_id: int
    nickname: str | None
    description: dict | None
    created_at: datetime | None
    updated_at: datetime | None
    comments: list[TgUserCommentSchema] | None

    class Config:
        from_attributes = True
