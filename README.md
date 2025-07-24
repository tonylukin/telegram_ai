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

### Run consumers
```bash
PYTHONPATH=. python3 app/consumers/human_scanner_consumer.py
```

### Run script to generate news
- First with some count:
```bash
curl -X 'POST' 'http://127.0.0.1:8000/news/generate-texts' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{"count": 2}'
```
- Then with no count:
```bash
curl -X 'POST' 'http://127.0.0.1:8000/news/generate-texts' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{}'
```

### Run script to generate reactions
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/generate-reactions' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{}'
```

### Run script to generate messages to chats
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/generate-messages' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{"message": "news_luxury_narrator"}'

### Run script to generate comments to channels
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/generate-comments' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{"message": "news_luxury_narrator"}'
```

### Run script to invite users
```bash
curl -X 'POST' 'http://127.0.0.1:8000/chat/invite-users' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{"target_channels": []}'
```

### Get info by username
```bash
curl -X 'POST' 'http://127.0.0.1:8000/user-info/collect' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{"username": "", "chats": [""]}'
```

### Killing fastAPI debugger
```bash
lsof -i tcp:8000
kill -9 XXXXX
```