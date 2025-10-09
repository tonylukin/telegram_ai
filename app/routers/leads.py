from fastapi import APIRouter, Request, HTTPException
from fastapi.params import Depends

from app.services.leads.generator_from_channels import GeneratorFromChannels

router = APIRouter(prefix="/leads")

@router.post("/from-channels")
async def generate_leads_from_channels(request: Request, lead_generator: GeneratorFromChannels = Depends()):
    try:
        data = await request.json()
        result = await lead_generator.generate_from_telegram_channels(chats=data.get('chats'), condition=data.get('condition'), answers=data.get('answers', None))

        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
