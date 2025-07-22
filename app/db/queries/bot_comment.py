from sqlalchemy.orm import Session

from app.models.bot import Bot
from app.models.bot_comment import BotComment
from datetime import datetime, timedelta

def get_bot_comments(session: Session, bot: Bot, channel: str, hours: int = 24) -> list[Bot]:
    dt = datetime.now() - timedelta(hours=hours)
    return session.query(BotComment).filter_by(bot_id=bot.id, channel=channel).where(BotComment.created_at >= dt).all()

def get_channel_comments(session: Session, channel: str, hours: int = 24) -> list[Bot]:
    dt = datetime.now() - timedelta(hours=hours)
    return session.query(BotComment).filter_by(channel=channel).where(BotComment.created_at >= dt).all()