from typing import Optional

from fastapi.params import Depends
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.telegram.telegram_message_sender import send_telegram_message
from app.services.text_maker import TextMaker, TextMakerDependencyConfig

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
        for text in texts:
            if count is None:
                view = f"<strong>{text['person']} {text['emotion']} читает сегодняшние новости</strong> \n\n"
            else:
                view = f"<strong>{text['person']} {text['emotion']} читает новость</strong> \n\n"
            view += f"{text['generated']}\n"
            view += f"<blockquote>{text['original']}</blockquote>"
            result &= send_telegram_message(view, text['image'])

        return {"status": "ok" if result else "error", "count": len(texts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-text-maker")
def test_text_maker(config: TextMakerDependencyConfig = Depends()):
    text_maker = TextMaker(config)
    text = text_maker.create_texts()
    return {"test": text}
