import base64
import boto3
import json
import os

DISHSCAN_BEDROCK_REGION = os.environ["DISHSCAN_BEDROCK_REGION"]
DISHSCAN_BEDROCK_MODEL_ID = os.environ["DISHSCAN_BEDROCK_MODEL_ID"]

bedrock = boto3.client("bedrock-runtime", region_name=DISHSCAN_BEDROCK_REGION)


def build_prompt(clarification_text: str | None = None) -> str:
    clarification_text = (clarification_text or "").strip()

    base_prompt = """
Вы — помощник по вопросам питания. Проанализируйте фотографию еды и оцените калорийность и макроэлементы.
Название еды, ингредиенты и другую информацию пишите на русском языке.

Правила:
1. Определите блюда на фото.
2. Оцените примерный вес каждого элемента.
3. Если пользователь прислал текстовое уточнение, считайте его более приоритетным источником правды для:
   - названия блюда
   - количества порций
   - веса
   - наличия или отсутствия соуса
   - напитков
   - ингредиентов, которые плохо видны на фото
4. Если уточнение пользователя противоречит визуальной догадке, отдавайте приоритет уточнению пользователя, если оно не является явно невозможным.
5. Не придумывайте лишние блюда, которых нет ни на фото, ни в уточнении пользователя.
6. Если пользователь пишет "не X, а Y", используйте Y.
7. Если пользователь пишет "без соуса", "без масла", "без сахара", обязательно учитывайте это.
8. Сумма total должна быть равна сумме items.
9. Верните СТРОГО ТОЛЬКО JSON без markdown, без пояснений, без ```json.

Верните JSON по следующей схеме:
{
  "items":[
    {
      "name":"...",
      "estimated_grams":123,
      "calories":123,
      "protein_g":12,
      "fat_g":12,
      "carbs_g":12
    }
  ],
  "total":{
    "calories":123,
    "protein_g":12,
    "fat_g":12,
    "carbs_g":12
  },
  "assumptions":["..."],
  "confidence":0.0
}
""".strip()

    if clarification_text:
        base_prompt += f"""

ТЕКСТОВОЕ УТОЧНЕНИЕ ПОЛЬЗОВАТЕЛЯ:
{clarification_text}

Используйте это уточнение при расчёте.
""".rstrip()

    return base_prompt


def estimate_nutrition(image_bytes: bytes, clarification_text: str | None = None) -> dict:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    prompt = build_prompt(clarification_text)

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 800,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                ],
            }
        ],
    }

    resp = bedrock.invoke_model(
        modelId=DISHSCAN_BEDROCK_MODEL_ID,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )

    raw = resp["body"].read().decode("utf-8")
    data = json.loads(raw)
    text = data["content"][0]["text"].strip()

    if text.startswith("```json"):
        text = text.replace("```json", "").replace("```", "").strip()

    return json.loads(text)