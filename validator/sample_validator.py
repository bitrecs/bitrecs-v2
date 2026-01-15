import os
import secrets
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import yaml
import httpx
import random
import asyncio
import traceback
import utils.logger as logger
from dotenv import load_dotenv
load_dotenv()
import validator.config as config
import affinetes as af_env
from uuid import UUID
from typing import Any, Dict
from models.evaluation_run import EvaluationRunErrorCode, EvaluationRunStatus
from models.problem import ProblemTestResultStatus
from models.agent import Agent
from api.endpoints.validator_models import (
    ScreenerRegistrationRequest, ScreenerRegistrationResponse, 
    ValidatorDisconnectRequest, ValidatorFinishEvaluationRequest, 
    ValidatorHeartbeatRequest, ValidatorRegistrationRequest, 
    ValidatorRegistrationResponse, ValidatorRequestEvaluationRequest, 
    ValidatorRequestEvaluationResponse, ValidatorUpdateEvaluationRunRequest
)
from validator.http_utils import get_ridges_platform, post_ridges_platform
from evaluator.problem_suites.polygot.polyglot_suite import POLYGLOT_JS_SUITE, POLYGLOT_PY_SUITE
from queries.problem_statistics import SWEBENCH_VERIFIED_SUITE
from utils.git import COMMIT_HASH
from utils.system_metrics import get_system_metrics
from evaluator.models import EvaluationRunException

session_id: str | None = None

EVAL_TIMEOUT = (30, 600)
RETRY_SLEEP_ON_ERROR = 60
PARENT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


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


async def get_health_from_docker(url: str) -> dict | None:
    """Fetch heartbeat data from a Docker container."""
    try:
        timeout = (5, 10)    
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            data = response.json()
            return data
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching heartbeat from Docker: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Error fetching heartbeat from Docker: {e}")
    return None


async def try_get_run_log(run_id: str) -> str | None:
    """ Fetch run log from Docker container """
    af_hostname = "localhost"
    af_container_port = 8081
    timeout = (10, 60)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(
            f"http://{af_hostname}:{af_container_port}/run_log/{run_id}",
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            log = response.json()
            return log
        else:
            logger.error(f"Failed to get run log for {run_id}: {response.status_code}")
            return None


async def load_agent_by_evaluation_run(evaluation_run_id: UUID) -> Agent:
    """Load an agent by its evaluation run ID."""
    response = await get_ridges_platform(f"/agent/get-by-evaluation-run-id?evaluation_run_id={evaluation_run_id}", quiet=2)
    agent = Agent(**response)
    return agent


async def update_evaluation_run(evaluation_run_id: UUID, problem_name: str, updated_status: EvaluationRunStatus, extra: Dict[str, Any] = {}):
    logger.info(f"Updating evaluation run {evaluation_run_id} for problem {problem_name} to {updated_status.value}...")    
    await post_ridges_platform("/validator/update-evaluation-run", ValidatorUpdateEvaluationRunRequest(
        evaluation_run_id=evaluation_run_id,
        updated_status=updated_status,
        **(extra or {})
    ), bearer_token=session_id, quiet=2)
    

# Simulate a run of an evaluation run, useful for testing, set SIMULATE_EVALUATION_RUNS=True in .env
async def _simulate_run_evaluation_run(evaluation_run_id: UUID, problem_name: str):
    logger.info(f"Starting simulated evaluation run {evaluation_run_id} for problem {problem_name}...")

    SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS = random.choice([1, 3, 4])
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
    try:
        # Figure out what problem suite this problem belongs to
        #problem_suite = next((suite for suite in problem_suites if suite.has_problem_name(problem_name)), None)

        # If we don't have a problem suite that supports this problem, mark the evaluation run as errored
        # if problem_suite is None:
        #     await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.error, {
        #         "error_code": EvaluationRunErrorCode.VALIDATOR_UNKNOWN_PROBLEM.value,
        #         "error_message": f"The problem '{problem_name}' was not found in any problem suite"
        #     })
        #     return
        test = 1 + 1

        try:
             # Get the problem
            #problem = problem_suite.get_problem(problem_name)
            #logger.info(f"Starting evaluation run {evaluation_run_id} for problem {problem_name}...")

            miner_agent = await load_agent_by_evaluation_run(evaluation_run_id)
            if miner_agent is None:
                raise Exception(f"Agent not found for evaluation run {evaluation_run_id}")            

            logger.info("Loaded miner input YAML file successfully")
            logger.info(f"Miner Agent ID: {miner_agent.agent_id}")
            logger.info(f"Miner Agent Name: {miner_agent.name}")
            logger.info(f"Miner Agent Status: {miner_agent.status}")

            logger.info(f"Testing model: {miner_agent.model} with provider: {miner_agent.provider}")

            # Move from pending -> initializing_agent
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.initializing_agent)
            
            # Move from initializing_agent -> running_agent
            await asyncio.sleep(random.random() * config.SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS)
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.running_agent)           

            # Start initializing the agent sandbox
            openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
            chutes_api_key = os.environ.get("CHUTES_API_KEY")
            if not openrouter_api_key or not chutes_api_key:
                raise Exception("Missing required API keys for Affine ENV evaluation run")

            af_image = "ghcr.io/bitrecs/bitrecs-evals:main"
            af_mode = "docker"            
            af_hostname = "localhost"
            af_container_port = 8081
            af_run_token = secrets.token_hex(16)
            af_env_vars = {
                "BITRECS_RUN_TOKEN": af_run_token,
                "BITRECS_RUN_ID": str(evaluation_run_id),
                "OPENROUTER_API_KEY": openrouter_api_key,
                "CHUTES_API_KEY": chutes_api_key
            }
            env = af_env.load_env(
                image=af_image,
                mode=af_mode,
                env_vars=af_env_vars,                
                host_port=af_container_port,
                host_network=True,
                cleanup=False,
                force_recreate=True,                
                pull=True
            )
            if env is None:
                raise Exception("Failed to load Docker environment")
            logger.info("Loaded Docker environment successfully")

            af_health = await get_health_from_docker(f"http://{af_hostname}:{af_container_port}/health")
            if af_health is None:
                raise Exception("Failed to get heartbeat from Docker environment")
            if af_health["status"] != "healthy":
                raise Exception(f"Docker environment is not healthy: {af_health}")
        
            yaml_content = Agent.to_yaml(miner_agent)
            logger.info(f"Loaded YAML content from : {miner_agent.agent_id}")
            logger.info("Triggering evaluation in Affine environment...")

            # Move from running_agent -> initializing_eval
            await asyncio.sleep(random.random() * config.SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS)
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.initializing_eval, {
                "patch": "FAKE PATCH",
                "agent_logs": "FAKE AGENT LOGS"
            })

            await asyncio.sleep(random.random() * config.SIMULATE_EVALUATION_RUN_MAX_TIME_PER_STAGE_SECONDS)
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.running_eval)            
            
            logger.info(f"Run timeout set to: {EVAL_TIMEOUT[1]} seconds")
            async with httpx.AsyncClient(timeout=EVAL_TIMEOUT) as client:
                response = await client.post(
                    f"http://{af_hostname}:{af_container_port}/evaluate",
                    json={"yaml_content": yaml_content, "run_token": af_run_token},
                    headers={"Content-Type": "application/json"}
                )
                logger.info(f"Received response: {response.text}")
                response.raise_for_status()
                result = response.json()

            #logger.debug(f"RAW Evaluation result: {result}")
            tak_name = result.get("task_name", "N/A")
            run_id = result.get("run_id", "N/A")
            score = result.get("score", "N/A")
            success = result.get("success", "N/A")
            time_taken = result.get("time_taken", "N/A")
            extra = ""
            logger.info("Evaluation Result:")
            logger.info(f"  Task Name: {tak_name}")
            logger.info(f"  Run ID: {run_id}")
            logger.info(f"  Score: {score}")
            logger.info(f"  Success: {success}")
            logger.info(f"  Time Taken: {time_taken} seconds")           
            logger.info("  Extra:")
            if 'extra' in result and 'result' in result['extra']:
                logger.info(result['extra']['result'])
                extra = result['extra']['result']
            else:
                logger.info("    No extra details available")   
            
            run_log = await try_get_run_log(run_id)
            if run_log is None:
                logger.error("Failed to retrieve run log")
            this_log = run_log["report"] if run_log and "report" in run_log else "No report available"
            #extra = this_log

            # Cleanup
            await env.cleanup()    

            status = ProblemTestResultStatus.PASS if success else ProblemTestResultStatus.FAIL          
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.finished, {
                "test_results": [{"name": tak_name, "category": "default", "status": f"{status.value}"}],
                "eval_logs": this_log
            })
        except EvaluationRunException as e:
            logger.error(f"Evaluation run {evaluation_run_id} for problem {problem_name} errored: {e}")
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.error, {
                "error_code": e.error_code.value,
                "error_message": e.error_message
            })

        except Exception as e:
            logger.error(f"Evaluation run {evaluation_run_id} for problem {problem_name} errored: {EvaluationRunErrorCode.VALIDATOR_INTERNAL_ERROR.get_error_message()}: {e}")
            logger.error(traceback.format_exc())
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.error, {
                "error_code": EvaluationRunErrorCode.VALIDATOR_INTERNAL_ERROR.value,
                "error_message": f"{EvaluationRunErrorCode.VALIDATOR_INTERNAL_ERROR.get_error_message()}: {e}\n\nTraceback:\n{traceback.format_exc()}"
            })

        logger.info(f"Finished evaluation run {evaluation_run_id} for problem {problem_name}")

    except Exception as e:
        logger.error(f"Error in _run_evaluation_run(): {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        os._exit(1)
    


# Run an evaluation, automatically dispatches all runs to either _simulate_run_evaluation_run or _run_evaluation_run
async def _run_evaluation(request_evaluation_response: ValidatorRequestEvaluationResponse):
    logger.info("Received evaluation:")
    logger.info(f"  # of evaluation runs: {len(request_evaluation_response.evaluation_runs)}")

    for evaluation_run in request_evaluation_response.evaluation_runs:
        logger.info(f"    {evaluation_run.problem_name}")

    logger.info("Starting evaluation...")
    SIMULATE_EVALUATION_RUNS = False

    tasks = []
    for evaluation_run in request_evaluation_response.evaluation_runs:
        evaluation_run_id = evaluation_run.evaluation_run_id
        problem_name = evaluation_run.problem_name
      
        if SIMULATE_EVALUATION_RUNS:
            tasks.append(asyncio.create_task(_simulate_run_evaluation_run(evaluation_run_id, problem_name)))
            #tasks.append(asyncio.create_task(_simulate_run_evaluation_run_affine(evaluation_run_id, problem_name)))            
        else:
            tasks.append(asyncio.create_task(_run_evaluation_run(evaluation_run_id, problem_name, request_evaluation_response.agent_code)))

    await asyncio.gather(*tasks)

    if SIMULATE_EVALUATION_RUNS:
        logger.info("Finished SIMULATED evaluation")
    else:
        logger.info("Finished evaluation")

    try:
        await post_ridges_platform("/validator/finish-evaluation", ValidatorFinishEvaluationRequest(), bearer_token=session_id, quiet=1)
    except Exception as e:
        logger.error(f"Error finishing evaluation: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        await disconnect(f"Error finishing evaluation: {type(e).__name__}: {e}")
        


# Disconnect from the Bitrecs platform (called when the program exits)
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
    #latest_set_problems_data = await get_ridges_platform("/evaluation-sets/all-latest-set-problems", quiet=1)
    #latest_set_problems = [EvaluationSetProblem(**prob) for prob in latest_set_problems_data]
    #latest_set_problem_names = list({prob.problem_name for prob in latest_set_problems})
    
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
        try:
            await _run_evaluation(ValidatorRequestEvaluationResponse(**request_evaluation_response_data))
        except Exception as e:
            logger.error(f"Error running evaluation: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            
            await asyncio.sleep(RETRY_SLEEP_ON_ERROR)

 

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
