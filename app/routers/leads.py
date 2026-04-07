import json
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.params import Depends

from app.services.leads.generator_from_channels import GeneratorFromChannels
from app.services.leads.self_tuning_from_channel import SelfTuningFromChannel
from app.services.rags.hairdresser.main import run_workflow
from app.services.telegram.helpers import get_data_from_file_by_separator

router = APIRouter(prefix="/leads")

@router.post("/from-channels")
async def generate_leads_from_channels(request: Request, lead_generator: GeneratorFromChannels = Depends()):
    try:
        data = await request.json()
        if data.get('notification_chat_id'):
            lead_generator.set_notification_credentials(chat_id=data.get('notification_chat_id'), bot_token=data.get('bot_token', None))

        result = await lead_generator.generate_from_telegram_channels(
            chats=data.get('chats'),
            workflow=data.get('workflow'),
            except_users=data.get('except_users', None),
            answers=data.get('answers', None),
            bot_roles=data.get('bot_roles', None),
        )

        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/self-tuning")
async def self_tuning(request: Request, self_tuning_from_channel: SelfTuningFromChannel = Depends()):
    try:
        data = await request.json()
        result = await self_tuning_from_channel.tune(channel_name=data.get('channel_name'), user=data.get('user'), workflow=data.get('workflow'))
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ml-self-tuning")
async def self_tuning(request: Request, self_tuning_from_channel: SelfTuningFromChannel = Depends()):
    try:
        data = await request.json()
        result = await self_tuning_from_channel.create_ml_data(channel_name=data.get('channel_name'), user=data.get('user'), workflow=data.get('workflow'))
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test-rag")
async def test_rag():
    try:
        queries = get_data_from_file_by_separator("test_rag_queries.txt")

        output = []
        message_texts = []
        for i, message in enumerate(queries):
            message_texts.append(json.dumps(
                {"text": message, "id": i, "name": f"User{i}"},
                ensure_ascii=False)
            )

        if message_texts:
            result = run_workflow(message_texts)
            output.append(result.get('output', {}))
        # for query in queries:
        #     result = run_workflow([query])
        #     output.append(result.get('output', {}))
        return {"status": "ok", "result": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
