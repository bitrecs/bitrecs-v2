import os
import pytest
import affinetes as af_env
import asyncio
import logging

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
        host_network=True 
    )

    assert env is not None
    logger.info("Loaded Docker environment successfully")        
    
    result = await asyncio.wait_for(env.evaluate(
        model="deepseek-ai/DeepSeek-V3",
        base_url="https://llm.chutes.ai/v1",
        task_id=10
    ), timeout=30)

    print(result)  # {"score": 1.0, "success": True}
    assert result["score"] == 1.0
    assert result["success"] == True

