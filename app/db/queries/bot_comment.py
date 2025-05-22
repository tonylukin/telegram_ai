from app.db.session import Session
from app.models.bot import Bot
from app.models.bot_comment import BotComment
from datetime import datetime, timedelta

session = Session()

def get_bot_comments(bot: Bot, channel: str, hours: int = 24) -> list[Bot]:
    dt = datetime.now() - timedelta(hours=hours)
    return session.query(BotComment).filter_by(bot_id=bot.id, channel=channel).where(BotComment.created_at >= dt).all()