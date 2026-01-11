import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import httpx
import random
import asyncio
import traceback
import utils.logger as logger
from dotenv import load_dotenv
load_dotenv()
from uuid import UUID
from typing import Any, Dict
from models.evaluation_run import EvaluationRunStatus
from models.problem import ProblemTestResultStatus
from api.endpoints.validator_models import ScreenerRegistrationRequest, ScreenerRegistrationResponse, ValidatorDisconnectRequest, ValidatorHeartbeatRequest, ValidatorRegistrationRequest, ValidatorRegistrationResponse, ValidatorRequestEvaluationRequest, ValidatorRequestEvaluationResponse
from models.agent import Agent
from rules.agent_validator import validate_artifact_template
from validator.http_utils import get_ridges_platform, post_ridges_platform

from evaluator.problem_suites.polygot.polyglot_suite import POLYGLOT_JS_SUITE, POLYGLOT_PY_SUITE
from models.evaluation_set import EvaluationSetProblem
from queries.problem_statistics import SWEBENCH_VERIFIED_SUITE
from utils.git import COMMIT_HASH
from utils.system_metrics import get_system_metrics

import validator.config as config


SERVICE_URL = "http://localhost:8000"
FETCH_LIMIT = 20
SLEEP_INTERVAL = 60
RETRY_SLEEP = 15 


#logger = logging.getLogger(__name__)
#logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

session_id: str | None = None


# A loop that sends periodic heartbeats to the Ridges platform
async def send_heartbeat_loop():
    try:
        logger.info("Starting send heartbeat loop...")
        while True:
            logger.info("Sending heartbeat...")
            system_metrics = await get_system_metrics()
            await post_ridges_platform("/validator/heartbeat", ValidatorHeartbeatRequest(system_metrics=system_metrics), bearer_token=session_id, quiet=2)
            await asyncio.sleep(config.SEND_HEARTBEAT_INTERVAL_SECONDS)
    except Exception as e:
        logger.error(f"Error in send_heartbeat_loop(): {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        os._exit(1)


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


    SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS = random.choice([3, 5, 9])
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

async def get_session_id() -> str | None:
    timestamp = int(time.time())
    #signed_timestamp = config.VALIDATOR_HOTKEY.sign(str(timestamp)).hex()
    signed_timestamp = "TEST"
    hotkey = "5Dy9FDg5jshHS7MirAFrRsKiFa6GPRMaiHC4Zng4HAgyi8yf"
    commit_hash = "TEST HASH"
    session_id = None

    async with httpx.AsyncClient(base_url=SERVICE_URL) as client:   
        register_response = await client.post("/validator/register-as-validator", json=ValidatorRegistrationRequest(
            timestamp=timestamp,
            signed_timestamp=signed_timestamp,
            hotkey=hotkey,
            commit_hash=commit_hash           
        ).model_dump())
        if register_response.status_code != 200:
            logger.error(f"Error registering as validator: {register_response.status_code} - {register_response.text}")
            return None
        session_id = register_response.json().get("session_id")
        logger.info(f"Registered as validator with session ID: {session_id}")

    if not session_id:
        raise Exception("Failed to register as validator, no session ID received.")

    return session_id


async def validator_loop() -> None:
    """Main loop to continuously fetch and validate agents."""
    logger.info("Starting validator loop...")  
    
    while True:
        logger.info("Requesting an evaluation...")
        session_id = await get_session_id()
        if not session_id:
            logger.error("Failed to obtain session ID. Exiting validator loop.")
            await asyncio.sleep(RETRY_SLEEP)
            continue   
        
        url = f"{SERVICE_URL}/validator/request-evaluation"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=ValidatorRequestEvaluationRequest().model_dump(), headers={"Authorization": f"Bearer {session_id}"})
            if response.status_code != 200:
                logger.error(f"Error requesting evaluation: {response.status_code} - {response.text}")
                logger.error(f"{response}")
                await asyncio.sleep(RETRY_SLEEP)
                continue

            data = response.json()
            if data is None:
                logger.info("No evaluations available. Waiting...")
                await asyncio.sleep(SLEEP_INTERVAL)
                continue

            await _run_evaluation(ValidatorRequestEvaluationResponse(**data))


# Disconnect from the Ridges platform (called when the program exits)
async def disconnect(reason: str):
    if session_id is None:
        return
    
    try:
        logger.info("Disconnecting validator...")
        await post_ridges_platform("/validator/disconnect", ValidatorDisconnectRequest(reason=reason), bearer_token=session_id)
        logger.info("Disconnected validator")
    except Exception as e:
        logger.error(f"Error in disconnect(): {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        os._exit(1)


# Main loop
async def main():
    global session_id
    global running_agent_timeout_seconds
    global running_eval_timeout_seconds
    global max_evaluation_run_log_size_bytes
    #global sandbox_manager
    global problem_suites

    # Register with the Ridges platform, yielding us a session ID
    logger.info("Registering validator...")

    try:
        if config.MODE == "validator":
            # Get the current timestamp, and sign it with the validator hotkey
            timestamp = int(time.time())
            signed_timestamp = config.VALIDATOR_HOTKEY.sign(str(timestamp)).hex()
            
            register_response = ValidatorRegistrationResponse(**(await post_ridges_platform("/validator/register-as-validator", ValidatorRegistrationRequest(
                timestamp=timestamp,
                signed_timestamp=signed_timestamp,
                hotkey=config.VALIDATOR_HOTKEY.ss58_address,
                commit_hash=COMMIT_HASH
            ))))
        
        elif config.MODE == "screener":
            register_response = ScreenerRegistrationResponse(**(await post_ridges_platform("/validator/register-as-screener", ScreenerRegistrationRequest(
                name=config.SCREENER_NAME,
                password=config.SCREENER_PASSWORD,
                commit_hash=COMMIT_HASH
            ))))
    
    except httpx.HTTPStatusError as e:
        if config.UPDATE_AUTOMATICALLY and e.response.status_code == 426:
            logger.info("Updating...")
            #reset_local_repo(pathlib.Path(__file__).parent.parent, e.response.headers["X-Commit-Hash"])
            sys.exit(0)
        else:
            raise e
    
    session_id = register_response.session_id
    running_agent_timeout_seconds = register_response.running_agent_timeout_seconds
    running_eval_timeout_seconds = register_response.running_eval_timeout_seconds
    max_evaluation_run_log_size_bytes = register_response.max_evaluation_run_log_size_bytes

    logger.info("Registered validator:")
    logger.info(f"  Session ID: {session_id}")
    logger.info(f"  Running Agent Timeout: {running_agent_timeout_seconds} second(s)")
    logger.info(f"  Running Evaluation Timeout: {running_eval_timeout_seconds} second(s)")
    logger.info(f"  Max Evaluation Run Log Size: {max_evaluation_run_log_size_bytes} byte(s)")



    # Create the sandbox manager
   # sandbox_manager = SandboxManager(config.RIDGES_INFERENCE_GATEWAY_URL)

    # Load all problem suites
    problem_suites = [POLYGLOT_PY_SUITE, POLYGLOT_JS_SUITE, SWEBENCH_VERIFIED_SUITE]



    # Get all the problems in the latest set
    latest_set_problems_data = await get_ridges_platform("/evaluation-sets/all-latest-set-problems", quiet=1)
    latest_set_problems = [EvaluationSetProblem(**prob) for prob in latest_set_problems_data]
    latest_set_problem_names = list({prob.problem_name for prob in latest_set_problems})
    
    # Prebuild the images for the SWE-Bench Verified problems
    #SWEBENCH_VERIFIED_SUITE.prebuild_problem_images(latest_set_problem_names)

    # Start the send heartbeat loop
    asyncio.create_task(send_heartbeat_loop())

    if config.MODE == "validator":
        # Start the set weights loop
        #asyncio.create_task(set_weights_loop())
        logger.info("SETTING WEIGHTS SYNC LOOP AS VALIDATOR")
        pass

    # Loop forever, just keep requesting evaluations and running them
    while True:
        logger.info("Requesting an evaluation...")
        
        request_evaluation_response_data = await post_ridges_platform("/validator/request-evaluation", ValidatorRequestEvaluationRequest(), bearer_token=session_id, quiet=1)

        # If no evaluation is available, wait and try again
        if request_evaluation_response_data is None:
            logger.info(f"No evaluations available. Waiting for {config.REQUEST_EVALUATION_INTERVAL_SECONDS} seconds...")
            await asyncio.sleep(config.REQUEST_EVALUATION_INTERVAL_SECONDS)
            continue

        await _run_evaluation(ValidatorRequestEvaluationResponse(**request_evaluation_response_data))





if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt")
        asyncio.run(disconnect("Keyboard interrupt"))
        os._exit(1)
    except Exception as e:
        logger.error(f"Error in main(): {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        asyncio.run(disconnect(f"Error in main(): {type(e).__name__}: {e}"))
        os._exit(1)
