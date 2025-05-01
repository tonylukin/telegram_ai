### Run app
```bash
fastapi dev app/main.py
uvicorn app.main:app --reload
```

### Run channel messenger scripts
```bash
PYTHONPATH=. python3 app/console/channels_listener.py
PYTHONPATH=. python3 app/console/reaction_sender_command.py
```

### Run script to generate news
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/generate-texts' \
     -H 'Content-Type: application/json' \
     -d '{"count": 2}'
```

### Run script to generate reactions
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/generate-reactions' \
     -H 'Content-Type: application/json' \
     -d '{"query": "text"}'
```