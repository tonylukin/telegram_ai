from sqlalchemy.orm import Session
from sqlalchemy import cast, func
from sqlalchemy.dialects.postgresql import ARRAY, VARCHAR

from app.models.bot import Bot

def get_bots(session: Session, roles: list[str] = None, names: list[str] = None, limit: int = None, offset: int = None) -> list[Bot]:
    query = session.query(Bot)

    if roles:
        query = query.filter(Bot.roles.op("&&")(cast(roles, ARRAY(VARCHAR))))

    if names:
        query = query.filter(Bot.name.in_(names))

    query = query.filter(Bot.status.is_(None)).order_by(func.random())

    if limit:
        query = query.limit(limit)

    if offset:
        query = query.offset(offset)

    return query.all()
