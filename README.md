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
* `GET /` - root
* `GET /health` - health
* `GET /providers` - provider pings
* `GET /public_key` - public key

* `GET /miners` - get list of miners
* `GET /validators` - get list of validators

* `GET /artifact` - get a single artifact
* `GET /artifacts` - get multiple artifacts
* `POST /artifact` - submit an artifact

* `GET /top` - get top artifact 
* `GET /run` - get a run id
* `GET /runs` - get all runs

* `POST /v1/chat/completions` - Verified Proxy


## Run
```bash
uv sync
uv run uvicorn api.main:app
```

## Test
start the server first then:
```bash
uv run pytest
```