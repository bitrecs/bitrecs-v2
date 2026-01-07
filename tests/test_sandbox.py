import os
import httpx
import pytest
import affinetes as af_env
import asyncio
import logging

import yaml

logger = logging.getLogger(__name__)

PARENT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

@pytest.mark.asyncio
async def test_calculator_env():
    # Skip if Docker is not running
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
async def test_bitrecs_eval():
    env = af_env.load_env(
        image="ghcr.io/bitrecs/bitrecs-evals:main",
        env_vars={"OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY")}, 
        mode="docker",
        host_network=True,
        cleanup=False,
        force_recreate=True,
        host_port=8081,
        pull=True      
    )
    
    assert env is not None
    logger.info("Loaded Docker environment successfully")
    
    timeout = (30, 600)  # (connect timeout, read timeout)
    # Directly call the HTTP endpoint
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "http://localhost:8081/evaluate",
            json={
                "model": "deepseek-ai/DeepSeek-V3",
                "base_url": "https://llm.chutes.ai/v1",
                "task_id": 10
            }
        )
        logger.info(f"Received response: {response.text}")
        response.raise_for_status()
        result = response.json()
    
    print(f"Score: {result['score']}")
    
    # Cleanup
    await env.cleanup()


@pytest.mark.asyncio
async def test_bitrecs_eval_yaml():
    
    env = af_env.load_env(
        image="ghcr.io/bitrecs/bitrecs-evals:main",
        env_vars={"OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY")}, 
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
    yaml_content = yaml.dump(miner_input_data)
    logger.info(f"Loaded YAML content from : {yaml_file_path}")
    
    timeout = (30, 600)    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            "http://localhost:8081/evaluate",
            json={"yaml_content": yaml_content},
            headers={"Content-Type": "application/json"}
        )
        logger.info(f"Received response: {response.text}")
        response.raise_for_status()
        result = response.json()
    
    print(f"Evaluation Result: {result}")
    
    # Cleanup
    await env.cleanup()