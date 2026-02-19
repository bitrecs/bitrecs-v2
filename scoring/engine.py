import os
import httpx
import asyncio
import utils.logger as logger


def get_current_eval_set_id() -> int:    
    platform_url = os.environ.get("RIDGES_PLATFORM_URL", "")
    client = httpx.Client(base_url=platform_url)
    response = client.get("/scoring/latest-set-info")
    result = response.json()
    logger.info(f"Latest evaluation set info: {result}")
    if response.status_code == 200 and "latest_set_id" in result:
        return result["latest_set_id"]
    else:        
        logger.error(f"Failed to retrieve latest evaluation set ID: {response.status_code} - {response.text}")
        raise Exception("Failed to retrieve latest evaluation set ID")


async def calculate_scores():
    logger.info("Calculating scores...")
    current_set_id = get_current_eval_set_id()
    logger.info(f"Current evaluation set ID: {current_set_id}")
    # Placeholder for actual score calculation logic
    await asyncio.sleep(10)  # Simulate time-consuming calculation
    logger.info("Scores calculated successfully.")