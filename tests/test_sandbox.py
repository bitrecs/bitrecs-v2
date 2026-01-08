import os
import secrets
import httpx
import pytest
import affinetes as af_env
import logging
import yaml
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

PARENT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

@pytest.mark.asyncio
async def test_calculator_env():    
    try:
        import docker
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker daemon not running, skipping test")
        logger.warning("Docker daemon not running, skipping test")
    
    image_tag = af_env.build_image_from_env(
        env_path=os.path.join(PARENT_DIR, "sandbox/environments/calc"),
        image_tag="calculator:latest"
    )
    logger.info(f"Built Docker image with tag: {image_tag}")    
    
    env = af_env.load_env(
        image="calculator:latest",
        env_vars={"CHUTES_API_KEY": "your-api-key"}, 
        host_network=True,
        host_port=8080
    )

    assert env is not None
    logger.info("Loaded Docker environment successfully")        
    
    result = await env.evaluate(
        model="deepseek-ai/DeepSeek-V3",
        base_url="https://llm.chutes.ai/v1",
        task_id=10
    )
    print(result)  # {"score": 1.0, "success": True}
    assert result["score"] == 1.0
    assert result["success"] == True   




@pytest.mark.asyncio
async def test_bitrecs_eval_yaml():
    
    provider_keys = {
        "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY"),
        "CHUTES_API_KEY": os.environ.get("CHUTES_API_KEY"),
    }
    env = af_env.load_env(
        image="ghcr.io/bitrecs/bitrecs-evals:main",
        env_vars=provider_keys,
        mode="docker",
        host_network=True,
        cleanup=False,
        force_recreate=True,
        host_port=8081,
        pull=True
    )
    
    assert env is not None
    logger.info("Loaded Docker environment successfully")

    yaml_file_path = os.path.join(PARENT_DIR, "miner", "miner_input.yaml")
    with open(yaml_file_path, "r") as f:
        miner_input_data = yaml.safe_load(f)

    logger.info(f"Testing model: {miner_input_data.get('model', 'N/A')} with provider: {miner_input_data.get('provider', 'N/A')}")

    yaml_content = yaml.dump(miner_input_data)
    logger.info(f"Loaded YAML content from : {yaml_file_path}")
    
    timeout = (30, 600)    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "http://localhost:8081/evaluate",
            json={"yaml_content": yaml_content},
            headers={"Content-Type": "application/json"}
        )
        #logger.info(f"Received response: {response.text}")
        response.raise_for_status()
        result = response.json()
    
    
    print("Evaluation Result:")
    print(f"  Task Name: {result.get('task_name', 'N/A')}")
    print(f"  Run ID: {result.get('run_id', 'N/A')}")
    print(f"  Score: {result.get('score', 'N/A')}")
    print(f"  Success: {result.get('success', 'N/A')}")
    print(f"  Time Taken: {result.get('time_taken', 'N/A')}")
    print("  Extra:")
    if 'extra' in result and 'result' in result['extra']:
        print(result['extra']['result'])
    else:
        print("    No extra details available")   
    
    # Cleanup
    await env.cleanup()