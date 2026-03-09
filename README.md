# Bitrecs V2
A novel recommendation subnet. 

[X](https://x.com/bitrecs) | [Dashboard](https://www.dashboard.bitrecs.ai)

**What is Bitrecs V2?** 
Bitrecs V2 is a prompt evolution subnet which rewards miners who optimize an artifact, an object containing a prompt, model, temperature and other parameters against a rotating set of challenging ecommerce evlautions. Miners submit via CLI by burning Bitrecs' alpha token on chain.

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


