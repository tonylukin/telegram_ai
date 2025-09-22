from pydantic import BaseModel
from datetime import datetime

class BotSchema(BaseModel):
    id: int
    name: str
    created_at: datetime
    roles: list[str]

    class Config:
        from_attributes = True
