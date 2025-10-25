from sqlalchemy.orm import Session

from app.models.tg_post_reaction import TgPostReaction


def get_reaction_by_post_id_bot_id(session: Session, post_id: int, channel:str, bot_id: int) -> TgPostReaction | None:
    return session.query(TgPostReaction).filter_by(post_id=post_id, channel=channel, bot_id=bot_id).first()
