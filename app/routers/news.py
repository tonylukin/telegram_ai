from typing import Optional

from fastapi.params import Depends
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.telegram.telegram_message_sender import TelegramMessageSender
from app.services.text_maker import TextMaker, TextMakerDependencyConfig
from app.services.text_maker_smishno import TextMakerSmishno
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_SMISHNO_BOT_TOKEN, TELEGRAM_SMISHNO_CHAT_ID

router = APIRouter(prefix="/news", tags=["News"])

class GenerateTextBody(BaseModel):
    count: Optional[int] = None

@router.post("/generate-texts")
def generate_texts(body: GenerateTextBody, config: TextMakerDependencyConfig = Depends()):
    try:
        count = body.count
        text_maker = TextMaker(config)
        texts = text_maker.create_texts(count = count)
        result = True
        sender = TelegramMessageSender(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        for text in texts:
            if count is None:
                view = f"<strong>{text['person']} {text['emotion']} читает сегодняшние новости</strong> \n\n"
            else:
                view = f"<strong>{text['person']} {text['emotion']} читает новость</strong> \n\n"
            view += f"{text['generated']}\n"
            view += f"<blockquote>{text['original']}</blockquote>"
            result &= sender.send_telegram_message(message=view, image=text['image'])

        return {"status": "ok" if result else "error", "count": len(texts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-texts-smishno")
def generate_texts_smishno(text_maker: TextMakerSmishno = Depends()):
    try:
        sender = TelegramMessageSender(TELEGRAM_SMISHNO_BOT_TOKEN, TELEGRAM_SMISHNO_CHAT_ID)
        text = text_maker.create_text()
        result = True
        view = f"<strong>Анекдот сегодня {text['adjective']}</strong> \n\n"
        view += f"{text['generated']}\n"
        view += f"<blockquote>{text['original']}</blockquote>"
        result &= sender.send_telegram_message(message=view, image=text['image'])

        return {"status": "ok" if result else "error"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-text-maker")
def test_text_maker(text_maker: TextMakerSmishno = Depends()):
    text = text_maker.create_text()
    return {"test": text}
