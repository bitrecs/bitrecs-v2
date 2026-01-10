import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import httpx
import random
import asyncio
import utils.logger as logger

from uuid import UUID
from typing import Any, Dict
from models.evaluation_run import EvaluationRunStatus
from models.problem import ProblemTestResultStatus
from utils.debug_lock import DebugLock
from api.endpoints.validator_models import ValidatorRegistrationRequest, ValidatorRegistrationResponse, ValidatorRequestEvaluationRequest, ValidatorRequestEvaluationResponse
from models.agent import Agent
from rules.agent_validator import validate_artifact_template



SERVICE_URL = "http://localhost:8000"
FETCH_LIMIT = 20
SLEEP_INTERVAL = 60
RETRY_SLEEP = 15 


#logger = logging.getLogger(__name__)
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


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



async def update_evaluation_run(evaluation_run_id: UUID, problem_name: str, updated_status: EvaluationRunStatus, extra: Dict[str, Any] = {}):
    logger.info(f"Updating evaluation run {evaluation_run_id} for problem {problem_name} to {updated_status.value}...")
    
    # await post_ridges_platform("/validator/update-evaluation-run", ValidatorUpdateEvaluationRunRequest(
    #     evaluation_run_id=evaluation_run_id,
    #     updated_status=updated_status,
    #     **(extra or {})
    # ), bearer_token=session_id, quiet=2)



# Simulate a run of an evaluation run, useful for testing, set SIMULATE_EVALUATION_RUNS=True in .env
async def _simulate_run_evaluation_run(evaluation_run_id: UUID, problem_name: str):
    logger.info(f"Starting simulated evaluation run {evaluation_run_id} for problem {problem_name}...")


    SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS =1
    # Move from pending -> initializing_agent
    await asyncio.sleep(random.random() * SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS)
    await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.initializing_agent)

    # Move from initializing_agent -> running_agent
    await asyncio.sleep(random.random() * SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS)
    await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.running_agent)

    # Move from running_agent -> initializing_eval
    await asyncio.sleep(random.random() * SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS)
    await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.initializing_eval, {
        "patch": "FAKE PATCH",
        "agent_logs": "FAKE AGENT LOGS"
    })

    # Move from initializing_eval -> running_eval
    await asyncio.sleep(random.random() * SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS)
    await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.running_eval)

    # Move from running_eval -> finished
    await asyncio.sleep(random.random() * SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS)
    await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.finished, {
        "test_results": [{"name": "fake_test", "category": "default", "status": f"{ProblemTestResultStatus.PASS.value}"}],
        "eval_logs": "FAKE EVAL LOGS"
    })
    
    logger.info(f"Finished simulated evaluation run {evaluation_run_id} for problem {problem_name}")


# Run an evaluation run
async def _run_evaluation_run(evaluation_run_id: UUID, problem_name: str, agent_code: str):
    logger.info(f"Starting evaluation run {evaluation_run_id} for problem {problem_name}...")
    return

# Run an evaluation, automatically dispatches all runs to either _simulate_run_evaluation_run or _run_evaluation_run
async def _run_evaluation(request_evaluation_response: ValidatorRequestEvaluationResponse):
    logger.info("Received evaluation:")
    logger.info(f"  # of evaluation runs: {len(request_evaluation_response.evaluation_runs)}")

    for evaluation_run in request_evaluation_response.evaluation_runs:
        logger.info(f"    {evaluation_run.problem_name}")

    logger.info("Starting evaluation...")

    tasks = []
    for evaluation_run in request_evaluation_response.evaluation_runs:
        evaluation_run_id = evaluation_run.evaluation_run_id
        problem_name = evaluation_run.problem_name
        SIMULATE_EVALUATION_RUNS = True
        if SIMULATE_EVALUATION_RUNS:
            tasks.append(asyncio.create_task(_simulate_run_evaluation_run(evaluation_run_id, problem_name)))
        else:
            tasks.append(asyncio.create_task(_run_evaluation_run(evaluation_run_id, problem_name, request_evaluation_response.agent_code)))

    await asyncio.gather(*tasks)

    logger.info("Finished evaluation")

    #await post_ridges_platform("/validator/finish-evaluation", ValidatorFinishEvaluationRequest(), bearer_token=session_id, quiet=1)



async def validator_loop() -> None:
    """Main loop to continuously fetch and validate agents."""
    logger.info("Starting validator loop...")

    timestamp = int(time.time())
    #signed_timestamp = config.VALIDATOR_HOTKEY.sign(str(timestamp)).hex()

    signed_timestamp = "TEST"

    async with httpx.AsyncClient(base_url=SERVICE_URL) as client:   
        register_response = await client.post("/validator/register-as-validator", json=ValidatorRegistrationRequest(
            timestamp=timestamp,
            signed_timestamp=signed_timestamp,
            hotkey="test hotkey",
            commit_hash="TEST HASH"
        ).model_dump())
        if register_response.status_code != 200:
            logger.error(f"Error registering as validator: {register_response.status_code} - {register_response.text}")
            return
        session_id = register_response.json().get("session_id")
        logger.info(f"Registered as validator with session ID: {session_id}")
    
    if not session_id:
        raise Exception("Failed to register as validator, no session ID received.")
   
    while True:
        logger.info("Requesting an evaluation...")
        
        url = f"{SERVICE_URL}/validator/request-evaluation"
        #url = f"{SERVICE_URL}/request-evaluation"
        session_id = "test-session-id"  # In practice, this would be a real
        #request_evaluation_response_data = await post_ridges_platform("/validator/request-evaluation", ValidatorRequestEvaluationRequest(), bearer_token=session_id, quiet=1)
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=ValidatorRequestEvaluationRequest().model_dump(), headers={"Authorization": f"Bearer {session_id}"})
            if response.status_code != 200:
                logger.error(f"Error requesting evaluation: {response.status_code} - {response.text}")
                await asyncio.sleep(RETRY_SLEEP)
                continue

        # If no evaluation is available, wait and try again
        # if request_evaluation_response_data is None:
        #     logger.info(f"No evaluations available. Waiting for {config.REQUEST_EVALUATION_INTERVAL_SECONDS} seconds...")
        #     await asyncio.sleep(config.REQUEST_EVALUATION_INTERVAL_SECONDS)
        #     continue

        await _run_evaluation(ValidatorRequestEvaluationResponse(**response.json()))



if __name__ == "__main__":
    asyncio.run(validator_loop())