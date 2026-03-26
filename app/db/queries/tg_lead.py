from sqlalchemy.orm import Session

from app.models.tg_lead import TgLead

def get_tg_lead_by_post_id(session: Session, post_id: int, channel: str) -> TgLead | None:
    return session.query(TgLead).filter_by(post_id=post_id, channel=channel).first()

def get_tg_lead_by_message(session: Session, message: str, workflow: str) -> TgLead | None:
    return session.query(TgLead).filter_by(message=message, workflow = workflow).first()

def get_tg_leads_by_messages(session: Session, messages: list[str], workflow: str, reaction: int | None = None) -> list[TgLead]:
    query = session.query(TgLead).filter(TgLead.message.in_(messages), TgLead.workflow == workflow)
    if reaction is not None:
        query = query.filter(TgLead.reaction == reaction)
    return query.all()
