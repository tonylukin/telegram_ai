import json
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.params import Depends

from app.services.leads.generator_from_channels import GeneratorFromChannels
from app.services.leads.self_tuning_from_channel import SelfTuningFromChannel
from app.services.rags.hairdresser.main import run_workflow

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
        # Load queries from file, supporting multiline entries separated by a delimiter (e.g., "---")
        output_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(output_dir, exist_ok=True)
        queries_file = os.path.join(output_dir, "test_rag_queries.txt")
        if os.path.exists(queries_file):
            with open(queries_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Split queries by delimiter (e.g., three dashes on a line)
                queries = [q.strip() for q in content.split("\n---\n") if q.strip()]
        else:
            queries = []

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
