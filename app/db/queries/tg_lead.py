from sqlalchemy.orm import Session

from app.models.tg_lead import TgLead

def get_tg_lead_by_post_id(session: Session, post_id: int) -> TgLead | None:
    return session.query(TgLead).filter_by(post_id=post_id).first()
