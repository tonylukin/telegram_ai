from sqlalchemy.orm import Session, load_only
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import ARRAY, VARCHAR

from app.models.bot import Bot

def get_bots(session: Session, roles: list[str] = None) -> list[Bot]:
    query = session.query(Bot).options(
        load_only(Bot.id, Bot.name, Bot.app_id, Bot.app_token, Bot.roles)
    )

    if roles:
        query = query.filter(Bot.roles.op("&&")(cast(roles, ARRAY(VARCHAR))))

    return query.all()
