from sqlalchemy.orm import Session
from sqlalchemy import cast, func
from sqlalchemy.dialects.postgresql import ARRAY, VARCHAR

from app.models.bot import Bot

def get_bots(session: Session, roles: list[str] = None, limit: int = None) -> list[Bot]:
    query = session.query(Bot)

    if roles:
        query = query.filter(Bot.roles.op("&&")(cast(roles, ARRAY(VARCHAR))))

    query = query.filter(Bot.status.is_(None)).order_by(func.random())

    if limit:
        query = query.limit(limit)

    return query.all()
