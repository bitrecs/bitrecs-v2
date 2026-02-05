# Bitrecs V2

V2

## Configure Environment

### `.env` (server)
```
B64_PRIVATE_KEY=ed25519 key - required
CHUTES_API_KEY=ch key - required
HUGGING_FACE_KEY=hfid key
OPEN_ROUTER_KEY=or key
CHAT_GPT_KEY=cg key
```

### `/tests/.env` (testing)
```
OPENROUTER_KEY=sk-or-v1-xxxxx
HOTKEY=your-miner-hotkey
```

## Endpoints

Server runs on `http://127.0.0.1:8000`

Docs

`http://127.0.0.1:8000/docs`

## Run
```bash
uv sync

uv run uvicorn api.main:app --access-log --log-level debug

```

## Docker

# Validator
```
docker compose -f validator/docker-compose.yml build
docker compose -f validator/docker-compose.yml up

```

## Test
start the server first then:
```bash
uv run pytest
```