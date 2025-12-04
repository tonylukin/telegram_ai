from fastapi import APIRouter, Request, HTTPException
from fastapi.params import Depends

from app.config import TELEGRAM_NOTIFICATIONS_CHAT_ID
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

@router.get("/test-rag")
async def test_rag():
    try:
        queries = [
            "Добрый вечер! Нужна модель для окрашивания. Оплата только за материал.Подробности в личку. Спасибо🌸", # super neg
            "Посоветуйте специалиста кто делает ботокс - филеры- нитки - ну и все остальное что поможет стать красавицей",
            "Сходила к Гале, очень крутой мастер. За 1 процедуру исправила мне мои поврежденные волосы, теперь у меня легкие, гладкие и шелковистые",
            "Привет! Меня зовут **Марина**, я дипломированный мастер по наращиванию волос ✨Работаю в Newport Beach (Orange County)",
            "Хочу покрасить волосы в красный цвет, посоветуйте мастера",
            "Нужен мастер по стрижке мужских волос в Лос-Анджелесе",
            "Ищу салон красоты для окрашивания волос в блонд",
            "Девчата - Подскажите мастера по волосам в салоне в Irvine? Не на дому. Благодарю", #pos
            "Девушки, кто-нибудь может макияж и прическу сделать в следующую субботу 15 ноября в районе 12?", #pos
            "Нужна модель на окрашивание. Оплата за материал.", #neg
            "Лицензированный мастер парикмахер Алёна Петрова Звони чтобы узнать подробнее по телефону", #neg
        ]
        output = []
        result = run_workflow(queries)
        output.append(result.get('output', {}))
        # for query in queries:
        #     result = run_workflow([query])
        #     output.append(result.get('output', {}))
        return {"status": "ok", "result": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
