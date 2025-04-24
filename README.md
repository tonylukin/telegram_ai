### Run app
```bash
fastapi dev app/main.py
uvicorn app.main:app --reload
```

### Run channel messenger script
```bash
PYTHONPATH=. python3 app/channels_listener.py
```

### Run script to generate news
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/generate-texts' \
     -H 'Content-Type: application/json' \
     -d '{"count": 2}'
```