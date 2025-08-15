### Run app
```bash
fastapi dev app/main.py
uvicorn app.main:app --reload
```

### Run channel messenger scripts
#### Listen for channels to comment new posts
```bash
PYTHONPATH=. python3 app/console/channels_listener.py
```
#### Find channels by query and react to it's posts
```bash
PYTHONPATH=. python3 app/console/reaction_sender_command.py
```
#### Invite all bots to my channels (as admins)
```bash
PYTHONPATH=. python3 app/console/invite_to_own_channels_command.py
```
#### Export popular channels to CSV
```bash
PYTHONPATH=. python3 app/console/channels_export_command.py
```
#### Export popular channels to CSV
```bash
PYTHONPATH=. python3 app/console/client_messages_listener.py --bot=
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

### Get info by username (Telegram)
```bash
curl -X 'POST' 'http://127.0.0.1:8000/user-info/collect' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{"username": "", "chats": [""]}'
```

### Get info by username (Instagram)
```bash
curl -X 'POST' 'http://127.0.0.1:8000/user-info/ig-collect' \
     -H 'Content-Type: application/json' \
     -H 'Authorization: Bearer 123' \
     -d '{"username": ""}'
```

### Killing fastAPI debugger
```bash
lsof -i tcp:8000
kill -9 XXXXX
```

### Copy sessions
```bash
scp sessions/* tgai:/home/telegram_ai/sessions/
```

### TESTS
```bash
PYTHONPATH=. pytest -v
```