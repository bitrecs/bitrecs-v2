import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import gc
import time
import uuid
import secrets
import asyncio
import traceback
import threading
import tracemalloc
import utils.logger as logger
from dotenv import load_dotenv
load_dotenv()
from api import config
from api.auth import APIKeyMiddleware
from queries.auth_key import load_keys
from api.db_sync import r2_download_and_sync
from utils.version import load_version_info
from utils.subtensor import get_subtensor
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, Request
from slowapi.middleware import SlowAPIMiddleware
from models.agent import Agent
from rules.agent_validator import validate_artifact_template
from queries.agent import (
    create_agent, get_agent_count, 
    record_upload_attempt
)
from queries.evaluation import set_all_unfinished_evaluation_runs_to_errored
from utils.database import (
    deinitialize_database, initialize_database, 
    check_database_health, DB_POOL
)
from api.utils.upload_agent_helpers import (
    check_agent_banned, check_if_gist_used, 
    check_if_hotkey_is_validator, check_if_hotkey_used    
)
from utils.network import get_client_ip
from utils.bittensor import is_hotkey_valid_format
from api.endpoints.validator import get_connected_validators_info, router as validator_router
from api.endpoints.debug import router as debug_router
from api.endpoints.agent import router as agent_router
from api.endpoints.evaluation_run import router as evaluation_run_router
from api.endpoints.evaluations import router as evaluations_router
from api.endpoints.evaluation_sets import router as evaluation_sets_router
from api.endpoints.scoring import router as scoring_router
from api.endpoints.statistics import router as statistics_router
from api.endpoints.retrieval import router as retrieval_router
from api.endpoints.dashboard import router as dashboard_router
from api.endpoints.backup import router as backup_router
from api.heartbeat import validator_heartbeat_timeout_loop
from llm.open_router import OpenRouter
from rules.agent_comparer import AgentComparer
from utils.r2 import validate_r2_bucket_connection
from version import __version__ as this_version
from api.utils.limiter import limiter
from models.miner_submission import MinerSubmission
from utils.gist import get_gist, get_gist_created_at
from utils.verify import (
    verify_submission_signature, verify_timestamp, 
    verify_transport_signature
)
from utils.commitment import is_commitment_valid
from queries.hotkey_gist import log_hotkey_gist
from queries.payments import record_evaluation_payment, retrieve_payment_by_hash
from models.payments import UploadPriceResponse, AgentUploadResponse, ErrorResponse
from utils.coingecko import get_bitrecs_price
from cachetools import TTLCache, cached
from utils.taostats import get_value_from_alpha


BT_NETWORK = os.environ.get("BT_NETWORK", "test")
BT_NETUID = int(os.environ.get("BT_NETUID", 296))

#COSINE_COMPARE_ENABLED = os.environ.get("COSINE_COMPARE_ENABLED", "true").lower() == "true"
COSINE_COMPARE_ENABLED = False
SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD", "0.0001"))

@asynccontextmanager
async def lifespan(app: FastAPI):    
    logger.info("V2 Server starting up")
    tracemalloc.start()

    app.state.last_updated = None
    app.state.total_requests = 0
    app.state.exceptions = 0    
    
    await initialize_database(
        username=config.DATABASE_USERNAME,
        password=config.DATABASE_PASSWORD,
        host=config.DATABASE_HOST,
        port=config.DATABASE_PORT,
        name=config.DATABASE_NAME
    )

    await validate_r2_bucket_connection(
        bucket=config.R2_BUCKET_NAME,
        access_key_id=config.R2_ACCESS_KEY_ID,
        secret_access_key=config.R2_SECRET_ACCESS_KEY,
        endpoint_url=config.R2_ENDPOINT_URL
    )
    
    app.state.heartbeat_task = asyncio.create_task(validator_heartbeat_timeout_loop())
    app.state.r2_sync_task = asyncio.create_task(r2_download_and_sync())
    app.state.api_keys = await load_keys()
    logger.info(f"Loaded {len(app.state.api_keys)} API keys from database")
    if len(app.state.api_keys) == 0:
        raise Exception("Fatal error: No API keys loaded from database. Shutting down.")
  
    try:
        logger.info(f"V2 API STARTED version: {this_version}")
        await set_all_unfinished_evaluation_runs_to_errored(error_message="Platform crashed while running this evaluation")
        yield
    finally:
        logger.info("Starting shutdown...")        
        app.state.heartbeat_task.cancel()        
        app.state.r2_sync_task.cancel()
        try:                      
            await app.state.heartbeat_task            
            await app.state.r2_sync_task
        except asyncio.CancelledError:
            pass

        if DB_POOL:
            logger.info("Deinitializing database...")
            try:
                await deinitialize_database()
            except Exception as e:
                logger.error(f"Error closing DB pool: {e}")
        
        gc.collect()
        logger.info(f"Shutdown complete. Final thread count: {threading.active_count()}")


version_info = load_version_info()
app_version = version_info if version_info else "2.0"
library_version = this_version

app = FastAPI(
    title=f"Bitrecs V2 Testnet API ({library_version})",
    version=app_version,
    description=f"(Netuid: {BT_NETWORK} - Network: {BT_NETUID})",
    debug=False,
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(APIKeyMiddleware)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "detail": str(exc)}
    )


app.include_router(retrieval_router, prefix="/retrieval")
app.include_router(scoring_router, prefix="/scoring")
app.include_router(validator_router, prefix="/validator")
app.include_router(evaluation_sets_router, prefix="/evaluation-sets")
app.include_router(debug_router, prefix="/debug")
app.include_router(agent_router, prefix="/agent")
app.include_router(evaluation_run_router, prefix="/evaluation-run")
app.include_router(evaluations_router, prefix="/evaluation")
app.include_router(statistics_router, prefix="/statistics")
app.include_router(dashboard_router, prefix="/dashboard")
app.include_router(backup_router, prefix="/backup")


@app.get("/")
@limiter.limit("60/minute")
async def read_root(request: Request):
    ts = str(int(time.time()))
    request_ip = get_client_ip(request)
    logger.info(f"Root endpoint accessed from IP {request_ip} at {ts}")
    return JSONResponse(
        status_code=200,
        content={"message": "Bitrecs V2 Testnet ⛏️",
                 "ts": str(ts), 
                 "network": BT_NETWORK,
                 "uid": BT_NETUID,
                 "total_requests": app.state.total_requests,
                 "exceptions": app.state.exceptions })


@app.get("/health")
@limiter.limit("60/minute")
async def health(request: Request):
    client_ip = get_client_ip(request)
    logger.info(f"Health check from IP: {client_ip}")   
    thread_count = threading.active_count()
    message = "OK"
    status = "healthy"
    if thread_count > 10:
        message = "WARNING: High thread count"
        status = "degraded"
        logger.warning(f"High thread count: {thread_count}")
        logger.warning("Active threads:")
        for thread in threading.enumerate():
            logger.warning(f"  - {thread.name} (daemon={thread.daemon}, alive={thread.is_alive()})")

    if thread_count > 50:
        status = "critical"
        message = "CRITICAL: Very high thread count"       
        logger.error(f"CRITICAL: Thread count {thread_count}")            
    
    current, peak = tracemalloc.get_traced_memory()
    version_file = load_version_info()

    db_health = await check_database_health()
    db_status = "OK" if db_health else "ERROR"
    agent_count = await get_agent_count()
    validator_info = get_connected_validators_info()
     
    return {
        "status": status,
        "nodes": 0,
        "db_status": db_status,
        "total_requests": app.state.total_requests,
        "exceptions": app.state.exceptions,
        "agent_count": agent_count,
        "validators": validator_info,
        "similarity_threshold": str(SIMILARITY_THRESHOLD) if COSINE_COMPARE_ENABLED else "DISABLED",
        "threads": thread_count,     
        "memory_current_mb": round(current / 1024 / 1024, 2),
        "memory_peak_mb": round(peak / 1024 / 1024, 2),        
        "message": message,
        "version": version_file.strip() if version_file else "N/A"        
    }


async def ensure_min_validators() -> None:
    validator_info = get_connected_validators_info()
    connected_validators = validator_info.get("connected_validators", 0)
    if connected_validators < config.NUM_EVALS_PER_AGENT:
        raise HTTPException(
            status_code=503,
            detail=f"Not enough validators available for evaluation (connected: {connected_validators})"
        )


async def calculate_upload_price() -> UploadPriceResponse:
    """Price of participation"""
    PRICE_BUFFER = 1.1
    BITRECS_PRICE = await get_bitrecs_price()
    eval_cost_usd = config.COST_PER_MINER_SUBMISSION_USD
    eval_cost_alpha = eval_cost_usd / BITRECS_PRICE
    amount_rao = int(eval_cost_alpha * 1e9 * PRICE_BUFFER)
    return UploadPriceResponse(
        amount_rao=amount_rao,
        bitrecs_price_usd=BITRECS_PRICE
    )


@app.get(
    "/eval-pricing",    
    tags=["cli"],
    response_model=UploadPriceResponse
)
@limiter.limit("60/minute")
@cached(cache=TTLCache(maxsize=1, ttl=1800), lock=asyncio.Lock())
async def get_upload_price(request: Request) -> UploadPriceResponse:
    client_ip = get_client_ip(request)
    logger.info(f"Upload price requested from IP {client_ip}")
    try:
        price_response = await calculate_upload_price()
        logger.info(f"Calculated upload price: {price_response.amount_rao} rao ")
        return price_response
    except Exception as e:
        logger.error(f"Error calculating upload price: {e}")
        raise HTTPException(status_code=500, detail="Error calculating upload price")
    

@app.post(
    "/check",
    tags=["cli"],
    response_model=AgentUploadResponse
)
@limiter.limit("60/minute")
async def check_agent_post(
    request: Request,
    submission: MinerSubmission   
) -> AgentUploadResponse:
    
    if config.DISALLOW_UPLOADS:
        raise HTTPException(
            status_code=503,
            detail=config.DISALLOW_UPLOADS_REASON
        )
    
    await ensure_min_validators()
    
    if not verify_submission_signature(submission):
        logger.warning(f"Invalid signature for submission from hotkey {submission.hotkey}")
        raise HTTPException(
            status_code=400,
            detail="Invalid signature for submission"
        )    
    
    miner_hotkey = submission.hotkey
    if not is_hotkey_valid_format(miner_hotkey):
        raise HTTPException(
            status_code=400,
            detail=f"Miner hotkey {miner_hotkey} is not a valid format"
        )
    
    await check_if_hotkey_is_validator(miner_hotkey)
    # latest_agent_created_at_in_latest_set_id = await get_latest_agent_created_at_for_miner_hotkey_in_latest_set_id(miner_hotkey=miner_hotkey)
    # if latest_agent_created_at_in_latest_set_id:
    #     check_rate_limit(latest_agent_created_at_in_latest_set_id)    
    
    if config.ENV == "prod":
        await check_if_hotkey_used(miner_hotkey)
        await check_if_gist_used(submission.gist_id)
        #await check_hotkey_registered(miner_hotkey)
        await check_agent_banned(miner_hotkey) 

    subtensor = await get_subtensor()
    coldkey = await subtensor.get_hotkey_owner(hotkey_ss58=miner_hotkey)
    stake_info = await subtensor.get_stake(
        coldkey_ss58=coldkey,
        hotkey_ss58=miner_hotkey,
        netuid=config.NETUID,
    )
    alpha_stake = stake_info.rao / 1e9
    upload_price = await calculate_upload_price()
    alpha_upload_requirement = upload_price.amount_rao / 1e9
    if alpha_stake < alpha_upload_requirement:
        logger.warning(f"Miner hotkey {miner_hotkey} has insufficient stake {alpha_stake} alpha to cover upload price of {alpha_upload_requirement} alpha")
        return JSONResponse(content={"error": "Insufficient stake to cover upload price"}, status_code=402)

    gist_created_at = get_gist_created_at(submission.gist_id)
    gist_raw_data = get_gist(submission.github_account, submission.gist_id)
    artifact_instance = Agent.from_yaml(gist_raw_data)
    if artifact_instance.agent_id is not None:
        return JSONResponse(content={"error": "agent_id must not be set by the client"}, status_code=400)
    
    validated, reason = validate_artifact_template(artifact_instance)
    if not validated:
        logger.warning(reason)
        return JSONResponse(content={"error": reason}, status_code=400)
    
    if submission.created_at != gist_created_at.isoformat():
        logger.warning(
            f"MinerSubmission created_at {submission.created_at} does not match Gist created_at {gist_created_at.isoformat()}"
        )
        return JSONResponse(content={"error": "created_at timestamp does not match Gist creation time"}, status_code=400)
    
    if artifact_instance.miner_hotkey.lower().strip() != submission.hotkey.lower().strip():
        logger.warning(
            f"MinerSubmission hotkey {submission.hotkey} does not match artifact miner_hotkey {artifact_instance.miner_hotkey}"
        )
        return JSONResponse(content={"error": "Miner hotkey in submission does not match miner hotkey in artifact"}, status_code=400)
    
    return AgentUploadResponse(
        status="success",
        message=f"Agent check successful"
    )



@app.post("/submit",
    tags=["cli"],
    response_model=AgentUploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request - Invalid input or validation failed"},
        402: {"model": ErrorResponse, "description": "Payment Required - Payment failed or insufficient funds"},
        409: {"model": ErrorResponse, "description": "Conflict - Upload request already processed"},
        429: {"model": ErrorResponse, "description": "Too Many Requests - Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Internal Server Error - Server-side processing failed"},
        503: {"model": ErrorResponse, "description": "Service Unavailable - No screeners available for evaluation"}
    })
@limiter.limit("60/minute")
async def miner_submission(request: Request, submission: MinerSubmission):
    client_ip = get_client_ip(request)
    logger.info(f"Submit artifact endpoint accessed from IP {client_ip}")
    request_id = secrets.token_hex(16)
    logger.info(f"Request ID: {request_id}")
    upload_data = {}
    if config.DISALLOW_UPLOADS:
        raise HTTPException(
            status_code=503,
            detail=config.DISALLOW_UPLOADS_REASON
        )

    await ensure_min_validators()

    try:
       
        x_signature = request.headers.get("X-Signature")
        x_timestamp = request.headers.get("X-Timestamp")       
        x_nonce = request.headers.get("X-Nonce")        
        payment_block_hash = request.headers.get("X-Payment-Block-Hash")
        payment_extrinsic_hash = request.headers.get("X-Payment-Extrinsic-Hash")        
        payment_extrinsic_index = request.headers.get("X-Payment-Extrinsic-Index")
        payment_amount_rao = int(request.headers.get("X-Payment-Amount-Rao"))
        if not verify_timestamp(x_timestamp):
            logger.warning(f"Invalid or expired timestamp: {x_timestamp}")
            raise HTTPException(status_code=400, detail="Invalid or expired timestamp")

        transport_signature_valid = verify_transport_signature(
            submission=submission,
            transport_signature=x_signature,
            payment_block_hash=payment_block_hash,
            payment_extrinsic_hash=payment_extrinsic_hash,
            payment_extrinsic_index=payment_extrinsic_index,
            amt_rao=payment_amount_rao,
            nonce=x_nonce
        )
        if not transport_signature_valid:
            logger.warning(f"Invalid transport signature for submission from hotkey {submission.hotkey}")
            raise HTTPException(status_code=400, detail="Invalid transport signature")

        if not verify_submission_signature(submission):
            logger.warning(f"Invalid signature for submission from hotkey {submission.hotkey}")
            raise HTTPException(status_code=400, detail="Invalid submission signature")
        
        await check_if_hotkey_is_validator(submission.hotkey)
        
        existing_payment = await retrieve_payment_by_hash(
            payment_block_hash=payment_block_hash,
            payment_extrinsic_index=payment_extrinsic_index
        )
        if existing_payment is not None:
            raise HTTPException(status_code=402, detail="Payment already used")
        
        onchain_payment_valid = await check_onchain_payment(
            miner_hotkey=submission.hotkey,
            payment_block_hash=payment_block_hash,
            payment_extrinsic_index=payment_extrinsic_index,
            amount_rao=payment_amount_rao
        )
        if not onchain_payment_valid:
            logger.warning("On-chain payment verification failed")
            raise HTTPException(status_code=402, detail="On-chain payment verification failed")              

        gist_created_at = get_gist_created_at(submission.gist_id)
        gist_raw_data = get_gist(submission.github_account, submission.gist_id)        
        artifact_instance = Agent.from_yaml(gist_raw_data)
        if artifact_instance.agent_id is not None:
            return JSONResponse(content={"error": "agent_id must not be set by the client"}, status_code=400)
        
        validated, reason = validate_artifact_template(artifact_instance)
        if not validated:
            logger.warning(reason)
            return JSONResponse(content={"error": reason}, status_code=400)
        
        if submission.created_at != gist_created_at.isoformat():
            logger.warning(
                f"MinerSubmission created_at {submission.created_at} does not match Gist created_at {gist_created_at.isoformat()}"
            )
            return JSONResponse(content={"error": "created_at timestamp does not match Gist creation time"}, status_code=400)
        
        if artifact_instance.miner_hotkey != submission.hotkey:
            logger.warning(
                f"MinerSubmission hotkey {submission.hotkey} does not match artifact miner_hotkey {artifact_instance.miner_hotkey}"
            )
            return JSONResponse(content={"error": "Miner hotkey in submission does not match miner hotkey in artifact"}, status_code=400)
        
        if config.ENV == "prod":
            await check_if_hotkey_used(submission.hotkey)     
            await check_if_gist_used(submission.gist_id)     

        #check chain commitment
        commit_valid, commit_block = await is_commitment_valid(submission)
        if not commit_valid:
            logger.warning(f"MinerSubmission commitment to chain is not valid for Gist {submission.gist_id}")
            return JSONResponse(content={"error": "Commitment to chain is not valid for this submission"}, status_code=400)
        else:
            logger.info(f"MinerSubmission commitment to chain is valid for Gist {submission.gist_id} from hotkey {submission.hotkey} on block {commit_block}")
        
        sub = await get_subtensor()
        miner_uid = await sub.get_uid_for_hotkey_on_subnet(hotkey_ss58=submission.hotkey, netuid=config.NETUID)
        coldkey = await sub.get_hotkey_owner(hotkey_ss58=submission.hotkey, block=int(commit_block))        
        artifact_instance.miner_uid = str(miner_uid)
        logger.info(f"Miner UID {miner_uid} for {submission.hotkey} from coldkey {coldkey}")

        # Assign UUID before similarity check (needed for embedding)
        artifact_instance.agent_id = uuid.uuid4()
        artifact_instance.ip_address = request_id #obfuscate IP with request ID for privacy

        similar_agents = []
        if COSINE_COMPARE_ENABLED and 1==2:
            logger.info("Cosine similarity check is ENABLED for artifact submissions")
            logger.info(f"Checking similarity for artifact ID: {artifact_instance.agent_id}")
            logger.info(f"Threshold: {SIMILARITY_THRESHOLD}")
            
            is_too_similar, similar_agents = await check_similar_agents(
                artifact_instance,
                similarity_threshold=SIMILARITY_THRESHOLD,
                max_results=5
            )
            
            if is_too_similar:                
                similar_details = [
                    {
                        "agent_id": str(agent_id),
                        "similarity_score": f"{1 - distance:.4f}",
                        "distance": f"{distance:.4f}"
                    }
                    for agent_id, distance in similar_agents
                ]                
                logger.warning(
                    f"Artifact submission rejected due to similarity: "
                    f"{[{'agent_id': agent_id, 'distance': distance} for agent_id, distance in similar_agents]}"
                )                
                return JSONResponse(
                    status_code=409,  # Conflict
                    content={
                        "error": "Agent is too similar to existing agents",
                        "message": "This agent appears to be a duplicate or very similar to existing submissions",
                        "similar_agents": similar_details,
                        "threshold": SIMILARITY_THRESHOLD
                    }
                )
            
        
        artifact_id = await create_agent(artifact_instance)
        await log_hotkey_gist(hotkey=submission.hotkey, 
                              gist=submission.gist_id, 
                              block=commit_block, 
                              artifact_id=artifact_id, 
                              uid=miner_uid, 
                              github_account=submission.github_account)
        logger.info(f"Artifact submitted successfully with ID: {artifact_id}")

        await record_evaluation_payment(
            payment_block_hash=payment_block_hash,
            payment_extrinsic_index=payment_extrinsic_index,
            amount_rao=payment_amount_rao,
            agent_id=artifact_instance.agent_id,
            miner_hotkey=artifact_instance.miner_hotkey,
            miner_coldkey=coldkey
        )

        upload_data = {
            'hotkey': artifact_instance.miner_hotkey,
            'agent_name': artifact_instance.name,
            'filename': "artifact.yaml",
            'file_size_bytes': Agent.token_count(artifact_instance),
            'ip_address': client_ip
        } 

        await record_upload_attempt(
            upload_type="agent",
            success=True,
            agent_id=artifact_instance.agent_id,
            http_status_code=201,
            **upload_data
        )
        
        response_content = {
            "request_id": request_id,
            "message": "Artifact submitted successfully",
            "artifact_id": str(artifact_id),
            "similarity_check": "passed",
            "similar_results": [{'agent_id': agent_id, 'distance': distance} for agent_id, distance in similar_agents]
        }
        return JSONResponse(status_code=201, content=response_content)
    
    except HTTPException:
        # Re-raise HTTPExceptions (they have specific status codes)
        raise
    except Exception as e:
        # Log full details for debugging
        logger.error(f"Error submitting artifact (request_id: {request_id}): {e}")        
        # Return verbose error in response (for dev/test; in prod, make it generic)
        error_details = {
            "error": "Failed to submit artifact",
            "details": str(e),  # Include exception message
            "request_id": request_id,
            #"traceback": traceback.format_exc() if config.ENV != "prod" else None  # Full traceback in non-prod
            "traceback": traceback.format_exc()
        }
        await record_upload_attempt(
            upload_type="agent",
            success=False,
            error_type='internal_error',
            error_message=str(e),
            http_status_code=500,
            **upload_data
        )
        return JSONResponse(content=error_details, status_code=400)



async def check_onchain_payment(miner_hotkey: str, payment_block_hash: str, payment_extrinsic_index: int, amount_rao: int) -> bool:    
    subtensor = await get_subtensor()
    try:
        payment_block = await subtensor.substrate.get_block(block_hash=payment_block_hash)
    except Exception as e:
        logger.error(f"Error retrieving payment block: {e}")
        raise HTTPException(
            status_code=402,
            detail="Payment could not be verified"
        )

    block_number = payment_block['header']['number']
    coldkey = await subtensor.get_hotkey_owner(hotkey_ss58=miner_hotkey, block=int(block_number))    
    payment_extrinsic = payment_block['extrinsics'][int(payment_extrinsic_index)]

    failed = await check_if_extrinsic_failed(payment_block_hash, int(payment_extrinsic_index))
    if failed:
        return False    
    
    onchain_payment_value_rao = None
    for arg in payment_extrinsic.value['call']['call_args']:
        if arg['name'] == 'amount' and arg['type'] == "AlphaCurrency":
            onchain_payment_value_rao = arg['value']
            break
    
    if onchain_payment_value_rao is None:
        raise HTTPException(
            status_code=402,
            detail="Payment value not found"
        )

    if int(onchain_payment_value_rao) != amount_rao:
        raise HTTPException(
            status_code=402,
            detail="Payment amount does not match"
        )
    
    # Make sure coldkey is the same as hotkeys owner coldkey
    if coldkey != payment_extrinsic['address']:
        raise HTTPException(
            status_code=402,
            detail="Coldkey does not match"
        )
    
    if 1==2:
        alpha_value = get_value_from_alpha(onchain_payment_value_rao)
        logger.info(f"On-chain payment verified for hotkey {miner_hotkey} with value {alpha_value} alpha (required: {amount_rao / 1e9} alpha)")

    return True


async def check_if_extrinsic_failed(block_hash: str, extrinsic_index: int) -> bool:
    subtensor = await get_subtensor()
    events = await subtensor.substrate.get_events(block_hash=block_hash)
    for event in events:
        if event.get("extrinsic_idx") != extrinsic_index:
            continue
        module = event["event"]["module_id"]
        event_id = event["event"]["event_id"]
        if module == "System" and event_id == "ExtrinsicFailed":
            return True
    return False


async def check_similar_agents(
    submitted_agent: Agent,
    similarity_threshold: float = 0.05,
    max_results: int = 5
) -> tuple[bool, list[tuple[str, float]]]:
    """
    Check if the submitted agent is too similar to existing agents.
    
    Args:
        submitted_agent: The agent to check
        similarity_threshold: Maximum allowed cosine distance (0.0 = identical, 0.1 = very similar)
        max_results: Maximum number of similar agents to return
    
    Returns:
        Tuple of (is_too_similar: bool, similar_agents: list[(agent_id, distance)])
    """   
    
    EMBEDDING_MODEL = "qwen/qwen3-embedding-8b"
    embedding_provider = OpenRouter(key=os.environ.get("OPENROUTER_API_KEY", ""),
                                   model=EMBEDDING_MODEL,
                                   embedding_dimensions=768)    
    agent_comparer = AgentComparer(provider=embedding_provider, use_db_cache=True)
    try:
        logger.info(f"Checking for similar agents to {submitted_agent.agent_id}")
        similar_agents = await agent_comparer.find_similar_agents(
            agent=submitted_agent,
            threshold=similarity_threshold,
            limit=max_results
        )
        
        if not similar_agents:
            logger.info(f"No similar agents found for {submitted_agent.agent_id}")
            return False, []
        
        # Check if any are too similar (below threshold)
        is_too_similar = any(distance < similarity_threshold for _, distance in similar_agents)
        
        if is_too_similar:
            logger.warning(
                f"Agent {submitted_agent.agent_id} is too similar to existing agents: "
                f"{[(agent_id, f'{dist:.4f}') for agent_id, dist in similar_agents]}"
            )
        else:
            logger.info(
                f"Agent {submitted_agent.agent_id} is unique enough. "
                f"Closest match: {similar_agents[0][1]:.4f}"
            )
        
        return is_too_similar, similar_agents
        
    except Exception as e:
        logger.error(f"Error checking for similar agents: {e}")
        # On error, allow submission (fail open)
        return False, []


if __name__ == "__main__":
    import uvicorn
    app.debug = True
    uvicorn.run(app, host="0.0.0.0", port=8000)