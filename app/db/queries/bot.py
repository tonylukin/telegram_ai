from sqlalchemy.orm import Session
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import ARRAY, VARCHAR

from app.models.bot import Bot

def get_bots(session: Session, roles: list[str] = None) -> list[Bot]:
    query = session.query(Bot)

    if roles:
        query = query.filter(Bot.roles.op("&&")(cast(roles, ARRAY(VARCHAR))))

    return query.all()
