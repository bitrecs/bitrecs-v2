# V2 Validator Setup

- We recommend Ubuntu 24+ LTS
- V2 validators do not require public IPs or open ports

# Update & Reboot
```
sudo apt-get update
sudo apt-get upgrade
```

# Install Docker

```sudo apt install apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update

apt-cache policy docker-ce

sudo apt install docker-ce

sudo systemctl status docker
```

# Install UV

```
curl -LsSf https://astral.sh/uv/install.sh | sh

reactivate shell:

source $HOME/.local/bin/env

```

# Setup Working Directory
```
mkdir bitrecs
cd bitrecs

Please ensure the folder is named bitrecs as docker compose expects ~/bitrecs
```

# Setup wallets
```
uv init
uv pip install bittensor-cli
uv add typing-extensions (if missing)
uv run btcli w regen-coldkeypub --ss58 COLDKEY_ADDR
uv run btcli w regen-hotkey
```


# Pull Images
```
docker pull ghcr.io/bitrecs/bitrecs-v2:main
docker pull ghcr.io/bitrecs/bitrecs-evals:main

if testing:

docker login ghcr.io -u YOUR_GITHUB_USERNAME -p YOUR_ACCESS_TOKEN
```

# Setup Env
```
touch .env

DEBUG=False

BITRECS_PLATFORM_URL=https://v2.api.bitrecs.ai
BITRECS_PLATFORM_API_KEY=
NETUID=296
SUBTENSOR_NETWORK=test
MODE="validator"
SCREENER_NAME=
SCREENER_PASSWORD=
SEND_HEARTBEAT_INTERVAL_SECONDS=20
SET_WEIGHTS_INTERVAL_SECONDS=3600
SET_WEIGHTS_TIMEOUT_SECONDS=90

VALIDATOR_WALLET_NAME=default
VALIDATOR_HOTKEY_NAME=default

CHECK_RUNNING_AGENTS_INTERVAL_SECONDS=60
CHECK_PENDING_EVALUATIONS_INTERVAL_SECONDS=30
CHECK_AGENT_UPLOAD_RATE_LIMIT_INTERVAL_SECONDS=600
R2_SYNC_INTERVAL_SECONDS=3600
REQUEST_EVALUATION_INTERVAL_SECONDS=45
SIMULATE_EVALUATION_RUNS=False
SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS=3

OPENROUTER_API_KEY=
CHUTES_API_KEY=


```

 # Docker Compose 
 
 ```
 copy .yml file into /bitrecs:
 
 https://github.com/bitrecs/bitrecs-v2/blob/main/validator/docker-compose-prod.yml

docker compose -f ./docker-compose-prod.yml up -d
```

# Logs
```
 docker compose -f docker-compose-prod.yml logs --tail 10 --follow
```
 