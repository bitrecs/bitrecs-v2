# Mining on Bitrecs

Mining on this subnet is done via submitting an artifact for evaluation. These artifacts are simple yaml files (prompts and parameters) that the system will test against a suite of evaluations.

The steps for a miner are:

- aquire fresh hotkey from subnet
- create an artifact.yaml
- test and tune artifact.yaml locally
- upload artifact to https://gist.github.com/ 
- take gist_id and run this command:

```
uv run bitrecs_cli3.py upload-burn --github-account mygithubaccount --gist-id 41bc02cec215b0149c5efdae4087f2cc --coldkey-name default --hotkey-name default
```

## Eval Process

Once your artifact has been uploaded it will go into an evaluation queue. This queue consists of 2 screeners and n validators. Each screener runs a specific set of basic evals to ensure data consistency. Once your artifact reaches the validator queue, it will be evalauted against a rotating set of evals to measure performance. Each validator computes the WTA miner and update the chain weights.

## Miner Setup

Install UV

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```
Clone repo
```
git clone repo
```
Sync and Setup Environment
```
uv sync
```
Create environment file
```
touch .env
SUBTENSOR_ADDRESS=wss://test.finney.opentensor.ai:443
SUBTENSOR_NETWORK=test
```

Submit artifact
```
uv run bitrecs_cli3.py upload-burn --github-account mygithubaccount --gist-id 41bc02cec215b0149c5efdae4087f2cc --coldkey-name default --hotkey-name default
```