
import os
import sys
import httpx
import asyncio
import logging
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.agent import Agent
from rules.agent_validator import validate_artifact_template


SERVICE_URL = "http://localhost:8000"
FETCH_LIMIT = 20
SLEEP_INTERVAL = 60
RETRY_SLEEP = 10  # seconds on error

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


async def fetch_agents(client: httpx.AsyncClient, limit: int) -> list[dict] | None:
    """Fetch a list of agents from the API."""
    try:
        response = await client.get(f"/artifacts?limit={limit}")
        response.raise_for_status()
        data = response.json()
        return data.get("artifacts", [])
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching agents: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Error fetching agents: {e}")
    return None


async def validate_agent(agent_data: dict) -> None:
    """Validate a single agent's template."""
    try:
        agent = Agent(**agent_data)
        validated, reason = validate_artifact_template(agent)
        if validated:
            logger.info(f"Agent {agent.agent_id} validated: {reason}")
            # TODO: Add actual evaluation/scoring logic here
        else:
            logger.warning(f"Agent {agent.agent_id} validation failed: {reason}")
    except Exception as e:
        agent_id = agent_data.get('agent_id', 'unknown')
        logger.error(f"Error validating agent {agent_id}: {e}")


async def validator_loop() -> None:
    """Main loop to continuously fetch and validate agents."""
    logger.info("Starting validator loop...")
    
    async with httpx.AsyncClient(base_url=SERVICE_URL) as client:
        while True:
            try:
                artifacts = await fetch_agents(client, FETCH_LIMIT)
                if artifacts:
                    for artifact_data in artifacts:
                        await validate_agent(artifact_data)
                else:
                    logger.warning("No artifacts fetched")
                
                logger.info(f"Sleeping for {SLEEP_INTERVAL} seconds")
                await asyncio.sleep(SLEEP_INTERVAL)
            
            except Exception as e:
                logger.error(f"Unexpected error in validator loop: {e} - retrying in {RETRY_SLEEP} seconds")
                await asyncio.sleep(RETRY_SLEEP)


if __name__ == "__main__":
    asyncio.run(validator_loop())