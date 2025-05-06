from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends

from app.services.telegram.reaction_sender import ReactionSender
from app.services.telegram.telegram_message_sender import send_telegram_message
from app.services.text_maker import TextMaker, TextMakerDependencyConfig
from pydantic import BaseModel

router = APIRouter(prefix="/chat", tags=["Chat"])

class GenerateTextBody(BaseModel):
    count: int

@router.post("/generate-texts")
def generate_texts(body: GenerateTextBody, config: TextMakerDependencyConfig = Depends()):
    try:
        count = body.count or 1
        text_maker = TextMaker(config)
        texts = text_maker.create_texts(count = count)
        result = True
        for text in texts:
            view = f"<strong>{text['person']} читает новость</strong> \n\n"
            view += f"{text['generated']}\n"
            view += f"<blockquote>{text['original']}</blockquote>"
            result &= send_telegram_message(view, text['image'])

        return {"status": "ok" if result else "error", "count": len(texts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class GenerateReactionsBody(BaseModel):
    query: Optional[str] = None

@router.post("/generate-reactions")
async def generate_reactions(body: GenerateReactionsBody, reaction_sender: ReactionSender = Depends()):
    try:
        result = await reaction_sender.send_reactions(query=body.query)
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test-text-maker")
def test_text_maker(config: TextMakerDependencyConfig = Depends()):
    text_maker = TextMaker(config)
    text = text_maker.create_texts()
    return {"test": text}
