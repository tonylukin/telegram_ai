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
     -d '{}'
```

### Run script to generate messages to chats
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/generate-messages' \
     -H 'Content-Type: application/json' \
     -d '{"message": "news_luxury_narrator"}'

### Run script to generate comments to channels
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/generate-comments' \
     -H 'Content-Type: application/json' \
     -d '{"message": "news_luxury_narrator"}'
```

### Killing fastAPI debugger
```bash
lsof -i tcp:8000
kill -9 XXXXX
```