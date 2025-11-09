from sqlalchemy.orm import Session

from app.models.tg_post_reaction import TgPostReaction


def get_reaction_by_post_id_and_channel(session: Session, post_id: int, channel:str) -> TgPostReaction | None:
    return session.query(TgPostReaction).filter_by(post_id=post_id, channel=channel).first()
