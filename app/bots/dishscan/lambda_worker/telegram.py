import json
import os
import urllib.request

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

def send_message(chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()
