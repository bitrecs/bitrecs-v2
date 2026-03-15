<div align="center">

# Bitrecs V2

<img src="docs/light-logo.svg#gh-light-mode-only" width="400" height="auto" alt="Bitrecs Logo"/>
<img src="docs/dark-logo.svg#gh-dark-mode-only" width="400" height="auto" alt="Bitrecs Logo"/>

[![Discord Chat](https://img.shields.io/discord/308323056592486420.svg)](https://discord.gg/bittensor)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) 

[X](https://x.com/bitrecs) • [Discord](https://discord.gg/bittensor) • [Website](https://bitrecs.ai/) • [Dashboard](https://dashboard.bitrecs.ai/)
</div>


**What is Bitrecs V2?** 

Bitrecs V2 is a prompt evolution subnet which rewards miners who optimize an artifact.yml, an object containing a prompt, model, temperature and other parameters against a rotating set of challenging ecommerce evaluations. Miners submit artifacts via the CLI by making an onchain commitment to begin evaluation.

**What does Bitrecs do?**

Bitrecs is a novel recommendation engine powered by Bittensor. Our flagship product is an ecommerce recommendation widget which drives sales for merchants by utilizing the newest state of the art models and novel generateive recommendation techniques. Merchants can expect to see personalized customer journey experinces drive higher average order values, resulting in more sales. 

## Validator

See [Validator Setup](docs/validator_setup.md)

## Miner

See [Miner Setup](docs/miner_setup.md)

## API

Create .env [Environment Example](api/.env.example)

```
uv sync
uv run uvicorn api.main:app --access-log --log-level debug
```

## V2 Flowchart

<img src="docs/v2_perseus_bitrecs.png" alt="Perseus V2" style="border: solid 3px #059669;" title="Bitrecs V2"/><sup>Bitrecs V2 separates prompt evolution from inference delivery</sup>


