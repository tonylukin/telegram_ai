import base64
import boto3
import json
import os

DISHSCAN_BEDROCK_REGION = os.environ["DISHSCAN_BEDROCK_REGION"]
DISHSCAN_BEDROCK_MODEL_ID = os.environ["DISHSCAN_BEDROCK_MODEL_ID"]

bedrock = boto3.client("bedrock-runtime", region_name=DISHSCAN_BEDROCK_REGION)


def estimate_nutrition(image_bytes: bytes) -> dict:
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
Вы — помощник по вопросам питания. Проанализируйте фотографию еды и оцените калорийность и макроэлементы.
Название еды, ингредиенты и другую информацию пишите на русском языке.
Верните СТРОГО ТОЛЬКО JSON по следующей схеме:
{
  "items":[{"name":"...", "estimated_grams":123, "calories":123, "protein_g":12, "fat_g":12, "carbs_g":12}],
  "total":{"calories":123, "protein_g":12, "fat_g":12, "carbs_g":12},
  "assumptions":["..."],
  "confidence":0.0
}
""".strip()

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