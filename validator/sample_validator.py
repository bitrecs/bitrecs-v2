import os
import sys
import httpx
import asyncio
import logging
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pathlib import Path
from models.agent import Agent
from rules.agent_validator import validate_artifact_template


ROOT_DIR = Path(__file__).parent.parent
SERVICE_URL = "http://localhost:8000"

logger = logging.getLogger(__name__)

async def validator_loop():
    logger.info("Starting validator loop...")
    while True:
        try:
            # Fetch agents from the API (example: get top agents)
            async with httpx.AsyncClient(base_url=SERVICE_URL) as client:
                response = await client.get("/artifacts?limit=10")
                if response.status_code == 200:
                    artifacts = response.json().get("artifacts", [])
                    for artifact_data in artifacts:
                        # Load and validate each agent
                        try:
                            agent = Agent(**artifact_data)
                            validated, reason = validate_artifact_template(agent)
                            if validated:
                                logger.info(f"Agent {agent.agent_id} validated: {reason}")
                                # Perform evaluation logic here (e.g., score the agent)
                            else:
                                logger.warning(f"Agent {agent.agent_id} validation failed: {reason}")
                        except Exception as e:
                            logger.error(f"Error validating agent {artifact_data.get('agent_id')}: {e}")
                else:
                    logger.error(f"Failed to fetch artifacts: {response.status_code} - {response.text}")
            
            # Sleep for a configurable interval (e.g., 60 seconds)
            logger.info("sleeping for 15")
            await asyncio.sleep(15)
        except Exception as e:
            logger.error(f"Error in validator loop: {e}")
            await asyncio.sleep(10)  # Brief pause before retrying
   

if __name__ == "__main__":
    import asyncio
    asyncio.run(validator_loop())