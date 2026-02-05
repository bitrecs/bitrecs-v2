import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import httpx
import random
import secrets
import asyncio
import traceback
import validator.config as config
import affinetes as af_env
import utils.logger as logger
from dotenv import load_dotenv
load_dotenv()
from uuid import UUID
from typing import Any, Dict
from utils.git import COMMIT_HASH
from utils.system_metrics import get_system_metrics
from models.agent import Agent
from api.endpoints.validator_models import (
    ScreenerRegistrationRequest, ScreenerRegistrationResponse, 
    ValidatorDisconnectRequest, ValidatorFinishEvaluationRequest, 
    ValidatorHeartbeatRequest, ValidatorRegistrationRequest, 
    ValidatorRegistrationResponse, ValidatorRequestEvaluationRequest, 
    ValidatorRequestEvaluationResponse, ValidatorUpdateEvaluationRunRequest
)
from models.problem import ProblemTestResult, ProblemTestResultStatus
from models.evaluation_run import EvaluationRunErrorCode, EvaluationRunStatus
from evaluator.models import EvaluationRunException
from models.eval_type import BitrecsEvaluationType
from validator.set_weights import set_weights_from_mapping
from validator.http_utils import get_ridges_platform, post_ridges_platform

session_id: str | None = None

EVAL_TIMEOUT = (30, 600)
RETRY_SLEEP_ON_ERROR = 60
PARENT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

async def set_weights_loop():
    logger.info("Starting set weights loop...")
    while True:
        weights_mapping = await get_ridges_platform("/scoring/weights", quiet=1)        
        try:
            await asyncio.wait_for(set_weights_from_mapping(weights_mapping), timeout=config.SET_WEIGHTS_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as e:
            logger.error(f"asyncio.TimeoutError in set_weights_from_mapping(): {e}")
        await asyncio.sleep(config.SET_WEIGHTS_INTERVAL_SECONDS)


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


import os
from pathlib import Path

def is_running_in_container() -> bool:
    """
    Detects if running inside a container (Docker, Podman, containerd, Kubernetes, etc.).
    Works reasonably well on:
    - Native Ubuntu / Debian / Fedora (cgroup v1 & v2)
    - WSL2 + Docker Desktop
    - Docker Desktop on macOS (inside the container)
    """
    # 1. Classic .dockerenv marker (exists in many Docker setups)
    if Path('/.dockerenv').exists():
        return True

    # 2. podman / some buildah / recent runtimes
    if Path('/run/.containerenv').exists():
        return True

    # 3. cgroup v1 & v2 style detection — most reliable signal
    cgroup_path = Path('/proc/1/cgroup')
    if cgroup_path.exists():
        try:
            content = cgroup_path.read_text(encoding='utf-8', errors='ignore')
            keywords = [
                'docker',           # classic docker cgroup v1
                'kubepods',         # kubernetes
                'containerd',       # containerd / k8s + containerd
                '/containers/',     # podman, some buildah
                'cri-o',            # CRI-O
                'libpod',           # podman
                # 'docker-ce'       # sometimes appears in Docker Desktop
            ]
            if any(kw in content for kw in keywords):
                return True

            # cgroup v2 unified hierarchy style (very common 2024+)
            # Look for non-root paths that indicate containerization
            lines = content.splitlines()
            for line in lines:
                parts = line.strip().split(':', 2)
                if len(parts) == 3:
                    _, controllers, path = parts
                    if path != '/' and (controllers or '0' in controllers or path.strip('/')):
                        # If it's not root AND has some container-like nesting
                        # Very conservative — catches most real containers
                        if any(c in path.lower() for c in ['docker', 'kubepods', 'containerd', 'cri-o', 'libpod']):
                            return True
                        # Many v2 setups just show long random hashes or /user.slice/...
                        # so we also return True if deeply nested (heuristics)
                        depth = len([p for p in path.split('/') if p])
                        if depth >= 3:  # arbitrary but works well in practice
                            return True
        except Exception:
            pass

    # 4. Last resort: check if we're namespaced in a way typical for containers
    # (not perfect, but helps in edge cases)
    try:
        if os.stat('/proc/1/ns/pid').st_ino != os.stat('/proc/self/ns/pid').st_ino:
            return True  # different PID namespace → almost certainly containerized
    except Exception:
        pass

    return False


async def get_health_from_docker(url: str) -> dict | None:
    logger.info(f"Attempting health check to: {url}")  # Add this
    try:
        async with httpx.AsyncClient(timeout=(10, 60)) as client:
            response = await client.get(url)
            logger.info(f"Health check response: {response.status_code} - {response.text}")  # Add this
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Health check HTTP error: {e.response.status_code} - {e.response.text}")  # Add this
    except Exception as e:
        logger.error(f"Health check failed: {e}")  # Add this
    return None

async def get_evals_from_docker(url: str) -> dict | None:
    """Fetch evals from a Docker container."""
    try:
        timeout = (10, 60)    
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            data = response.json()
            return data
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching evals from Docker: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Error fetching evals from Docker: {e}")
    return None

async def get_run_log_from_docker(run_id: str, port: int, hostname: str) -> str | None:
    """ Fetch run log from Docker container """
    timeout = (10, 60)
    try:        
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"http://{hostname}:{port}/run_log/{run_id}",
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                return response.json()                
            else:
                logger.error(f"Failed to get run log for {run_id}: {response.status_code}")
                return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching run log from Docker: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"Error fetching run log from Docker: {e}")
    return None   


async def load_agent_by_evaluation_run(evaluation_run_id: UUID) -> Agent:
    """Load an agent by its evaluation run ID."""
    response = await get_ridges_platform(f"/agent/get-by-evaluation-run-id?evaluation_run_id={evaluation_run_id}", quiet=2)
    agent = Agent(**response)
    return agent


async def update_evaluation_run(evaluation_run_id: UUID, problem_name: str, updated_status: EvaluationRunStatus, extra: Dict[str, Any] = {}):
    logger.info(f"Updating evaluation run {evaluation_run_id} for problem {problem_name} to {updated_status.value}...")
    
    max_retries = 5  # Number of retries for 401 errors
    for attempt in range(max_retries):
        try:
            await post_ridges_platform("/validator/update-evaluation-run", ValidatorUpdateEvaluationRunRequest(
                evaluation_run_id=evaluation_run_id,
                updated_status=updated_status,
                **(extra or {})
            ), bearer_token=session_id, quiet=2)
            return  # Success, exit
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and attempt < max_retries - 1:
                logger.warning(f"Session expired (401) on attempt {attempt + 1}. Re-registering and retrying...")
                await register_validator()
                continue  # Retry with new session
            else:
                raise  # Re-raise if not 401 or max retries hit

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
        
        is_docker = is_running_in_container()
        logger.info(f"Running in container: {is_docker}")
        eval_type = BitrecsEvaluationType(problem_name)
        sleeps = [2, 5, 7]
        sleep = secrets.choice(sleeps)
        logger.info(f"Sleeping for {sleep} seconds before {eval_type.value} ...")
        await asyncio.sleep(sleep)

        try:        

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
            if not any([openrouter_api_key, chutes_api_key]):
                raise Exception("Missing required API keys for Affine ENV evaluation run")

            bitrecs_run_id = str(evaluation_run_id)
            af_image = "ghcr.io/bitrecs/bitrecs-evals:main"
            af_mode = "docker"
            af_hostname = "localhost" if not is_running_in_container() else "bitrecs-evals-main"  # Container name for network access
            af_container_port = 8000  # Match affinetes' internal port (from logs: bitrecs-evals-main:8000)
            host_network = True if not is_docker else False
            
            af_run_token = secrets.token_hex(16)
            af_env_vars = {                
                "BITRECS_RUN_TOKEN": af_run_token,
                "BITRECS_RUN_ID": bitrecs_run_id,
                "OPENROUTER_API_KEY": openrouter_api_key,
                "CHUTES_API_KEY": chutes_api_key
            }
            env = af_env.load_env(
                image=af_image,
                mode=af_mode,
                env_vars=af_env_vars,                
                host_network=None,
                cleanup=False,
                force_recreate=True,
                #host_port=af_container_port,
                pull=False,
                network="bitrecs-network"
            )
            if env is None:
                raise Exception("Failed to load Docker environment")
            logger.info("Loaded Docker environment successfully")
            env.start_logging("bitrecs_eval.log")

            # Health check example (ensure URL matches)
            af_health = await get_health_from_docker(f"http://{af_hostname}:{af_container_port}/health")
            if af_health is None:
                raise Exception("Failed to get heartbeat from Docker environment")
            if af_health["status"] != "healthy":
                raise Exception(f"Docker environment is not healthy: {af_health}")
        
            yaml_content = Agent.to_yaml(miner_agent)
            logger.info(f"Loaded YAML content from : {miner_agent.agent_id}")
            logger.info("Triggering evaluation in Affine environment...")

            # Move from running_agent -> initializing_eval
            #await asyncio.sleep(random.random() * 3)
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.initializing_eval, {
                "patch": "initializing_eval",
                "agent_logs": f"run_id: {bitrecs_run_id}\nDocker container port: {af_container_port}\nDocker environment health: {af_health}"
            })

            await asyncio.sleep(random.random() * 2)
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.running_eval)     

            run_data = {"yaml_content": yaml_content, 
                        "run_token": af_run_token,
                        "problem_name": eval_type.value}
            
            logger.info(f"Run timeout set to: {EVAL_TIMEOUT[1]} seconds")
            logger.info(f"\033[32mRunning: {eval_type.value} evaluation... \033[0m")

            async with httpx.AsyncClient(timeout=EVAL_TIMEOUT) as client:
                response = await client.post(
                    f"http://{af_hostname}:{af_container_port}/evaluate",
                    json=run_data,
                    headers={"Content-Type": "application/json"}
                )
                logger.info(f"Received response: {response.text}")
                response.raise_for_status()
                result = response.json()

            #logger.debug(f"RAW Evaluation result: {result}")
            tak_name = result.get("task_name", "N/A")
            run_id = result.get("run_id", "N/A")
            score = result.get("score", 0.0)
            success = result.get("success", False)
            duration = result.get("duration", 0.0)
            extra = ""
            logger.info("Evaluation Result:")
            logger.info(f"  Run ID: {run_id}")
            logger.info(f"  Task Name: \033[32m{tak_name}\033[0m")
            logger.info(f"  Problem Name: \033[32m{problem_name}\033[0m")
            logger.info(f"  Eval Type: \033[32m{eval_type.value}\033[0m")            
            logger.info(f"\033[32m  Score: {score} \033[0m")
            logger.info(f"  Success: {success}")
            logger.info(f"  Duration: {duration} seconds")
            logger.info("  Extra:")
            if 'extra' in result and 'result' in result['extra']:
                logger.info(result['extra']['result'])
                extra = result['extra']['result']
            else:
                logger.info("    No extra details available")   
            
            run_log = await get_run_log_from_docker(run_id, af_container_port, af_hostname)
            if run_log is None:
                logger.error("Failed to retrieve run log")
            this_log = run_log["report"] if run_log and "report" in run_log else "No report available"            

            # Cleanup
            await env.cleanup()

            eval_status = ProblemTestResultStatus.PASS if success else ProblemTestResultStatus.FAIL
            eval_score = float(score) if isinstance(score, (int, float)) else None
            problem_test_result = ProblemTestResult(
                name=tak_name,
                category="default",
                status=eval_status,
                score=eval_score,
                duration=duration
            )
            await update_evaluation_run(evaluation_run_id, problem_name, EvaluationRunStatus.finished, {
                "test_results": [problem_test_result.model_dump()],
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
    



# Run an evaluation - serially
async def _run_evaluation(request_evaluation_response: ValidatorRequestEvaluationResponse):
    logger.info("Received evaluation:")
    logger.info(f"  # of evaluation runs: {len(request_evaluation_response.evaluation_runs)}")

    SIMULATE_EVALUATION_RUNS = False
    #SIMULATE_EVALUATION_RUNS = config.SIMULATE_EVALUATION_RUNSF

    # if len(request_evaluation_response.evaluation_runs) == 0:        
    #     logger.warning("No evaluation runs to process, finishing evaluation immediately.")
    #     logger.error("No evaluation runs to process.")
    #     await post_ridges_platform("/validator/finish-evaluation", ValidatorFinishEvaluationRequest(), bearer_token=session_id, quiet=1)
    #     return

    for evaluation_run in request_evaluation_response.evaluation_runs:
        logger.info(f"    {evaluation_run.problem_name}")

    logger.info("Starting evaluation...")

    for evaluation_run in request_evaluation_response.evaluation_runs:
        evaluation_run_id = evaluation_run.evaluation_run_id
        problem_name = evaluation_run.problem_name
      
        if SIMULATE_EVALUATION_RUNS:
            await _simulate_run_evaluation_run(evaluation_run_id, problem_name)            
        else:
            await _run_evaluation_run(evaluation_run_id, problem_name, request_evaluation_response.agent_code)

       
    try:
        await post_ridges_platform("/validator/finish-evaluation", ValidatorFinishEvaluationRequest(), bearer_token=session_id, quiet=1)
        if SIMULATE_EVALUATION_RUNS:
            logger.info("\033[33mFinished SIMULATED evaluation\033[0m")
        else:
            logger.info("\033[33mEVALUATION COMPLETE\033[0m")
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


async def register_validator():
    global session_id, running_agent_timeout_seconds, running_eval_timeout_seconds, max_evaluation_run_log_size_bytes
    max_registration_retries = 10
    registration_retry_delay = 60
    
    for attempt in range(max_registration_retries):
        try:
            logger.info(f"Registering validator... (attempt {attempt + 1}/{max_registration_retries})")
            
            if config.MODE == "validator":
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
            
            session_id = register_response.session_id
            running_agent_timeout_seconds = register_response.running_agent_timeout_seconds
            running_eval_timeout_seconds = register_response.running_eval_timeout_seconds
            max_evaluation_run_log_size_bytes = register_response.max_evaluation_run_log_size_bytes
            
            logger.info("Registered validator:")
            logger.info(f"  Session ID: {session_id}")
            logger.info(f"  Running Agent Timeout: {running_agent_timeout_seconds} second(s)")
            logger.info(f"  Running Evaluation Timeout: {running_eval_timeout_seconds} second(s)")
            logger.info(f"  Max Evaluation Run Log Size: {max_evaluation_run_log_size_bytes} byte(s)")
            
            break
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                logger.warning(f"Registration failed with 409 Conflict (attempt {attempt + 1}): {e.response.text}")
                if attempt < max_registration_retries - 1:
                    logger.info(f"Retrying registration in {registration_retry_delay} seconds...")
                    await asyncio.sleep(registration_retry_delay)
                else:
                    logger.error("Max registration retries reached. Exiting.")
                    raise
            elif config.UPDATE_AUTOMATICALLY and e.response.status_code == 426:
                logger.info("Updating...")
                sys.exit(0)
            else:
                raise
        except Exception as e:
            logger.error(f"Registration failed (attempt {attempt + 1}): {type(e).__name__}: {e}")
            if attempt < max_registration_retries - 1:
                logger.info(f"Retrying registration in {registration_retry_delay} seconds...")
                await asyncio.sleep(registration_retry_delay)
            else:
                logger.error("Max registration retries reached. Exiting.")
                raise

# Main loop
async def main():
    global session_id
    global running_agent_timeout_seconds
    global running_eval_timeout_seconds
    global max_evaluation_run_log_size_bytes        
    
    await register_validator()
    
    # Start the send heartbeat loop
    asyncio.create_task(send_heartbeat_loop())
    
    if config.MODE == "validator":
        
        asyncio.create_task(set_weights_loop())
        logger.info("SETTING WEIGHTS SYNC LOOP AS VALIDATOR")        
    
    # Loop forever, just keep requesting evaluations and running them
    while True:
        try:
            logger.info("Requesting an evaluation...")
            request_evaluation_response_data = await post_ridges_platform("/validator/request-evaluation", ValidatorRequestEvaluationRequest(), bearer_token=session_id, quiet=1)
            # If no evaluation is available, wait and try again
            if request_evaluation_response_data is None:
                logger.info(f"No evaluations available. Waiting for {config.REQUEST_EVALUATION_INTERVAL_SECONDS} seconds...")
                await asyncio.sleep(config.REQUEST_EVALUATION_INTERVAL_SECONDS)
                continue
            
            logger.info(f"Received evaluation with {request_evaluation_response_data}")
            await _run_evaluation(ValidatorRequestEvaluationResponse(**request_evaluation_response_data))
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.warning("Session expired (401). Re-registering...")
                await register_validator()
                continue  # Skip sleep and retry immediately with new session
            else:
                raise  # Re-raise for other HTTP errors
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
