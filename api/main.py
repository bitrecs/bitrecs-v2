import os
import gc
import time
import base64
import uuid
import httpx
import asyncio
import logging
import threading
import tracemalloc
from dotenv import load_dotenv
load_dotenv()

from models.agent import Agent
from rules.agent_validator import validate_artifact
from api import config
from cachetools import TTLCache
from typing import Tuple, Dict, Any
from models.product import Product
from models.llm_providers import LLMProviderStats
from utils.version import load_version_info
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from .metagraph_sync_manager import MetagraphSyncManager
from queries.agent import create_agent, get_agent_count, get_agents_by_top_limit
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi import FastAPI, Request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from utils.database import deinitialize_database, initialize_database, check_database_health, DB_POOL


log_level = logging.INFO    
logging.basicConfig(
    level=log_level,
    format='%(asctime)s | %(levelname)s | %(name)s:%(lineno)d - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


METAGRAPH_CACHE_DURATION = 3600  # 1 hour
PROVIDER_PING_CACHE = TTLCache(maxsize=10, ttl=3600) # 1 hour
REQUEST_HASH_HISTORY = TTLCache(maxsize=500_000, ttl=60 * 60 * 24)  # 24 hours
NONCE_HISTORY = TTLCache(maxsize=1_000_000, ttl=60 * 60 * 72)  # 72 hours


BT_NETWORK = os.environ.get("BT_NETWORK", "test")
BT_NETUID = int(os.environ.get("BT_NETUID", 296))
B64_PRIVATE_KEY = os.environ.get("B64_PRIVATE_KEY")
if not B64_PRIVATE_KEY:
    raise ValueError("B64_PRIVATE_KEY environment variable not set")
PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(base64.b64decode(B64_PRIVATE_KEY))
PUBLIC_KEY = PRIVATE_KEY.public_key()


http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0),
    limits=httpx.Limits(
        max_connections=100,
        max_keepalive_connections=15,
        keepalive_expiry=20.0
    )
)

metagraph_manager = MetagraphSyncManager(
    network=BT_NETWORK,
    netuid=BT_NETUID,
    sync_interval=METAGRAPH_CACHE_DURATION
)
metagraph_snapshot = {"nodes": {}}


async def check_hotkey_stake(
    hotkey: str,
    stake: float
) -> bool:
    if hotkey is None or stake is None:
        return False
    snapshot, _ = metagraph_manager.get_snapshot()
    node = snapshot.get(hotkey)
    logger.info(f"check_hotkey_stake {hotkey} : {node['stake'] if node else 'N/A'}, required {stake}")
    return node["stake"] >= stake if node else False


async def check_request_ip(
    hotkey: str,
    request_ip: str,
) -> bool:
    if hotkey is None or request_ip is None:
        return False
    snapshot, _ = metagraph_manager.get_snapshot()
    node = snapshot.get(hotkey)
    return node["ip"] == request_ip if node else False


def get_client_ip(request: Request) -> str:
    logger.debug(
        f"IP headers - x-real-ip: {request.headers.get('x-real-ip')}, "
        f"x-forwarded-for: {request.headers.get('x-forwarded-for')}, "
        f"do-connecting-ip: {request.headers.get('do-connecting-ip')}")
     
    if "do-connecting-ip" in request.headers:
        return request.headers.get('do-connecting-ip').strip()
    if "x-forwarded-for" in request.headers:
        forwarded_for = request.headers.get('x-forwarded-for')
        ips = [ip.strip() for ip in forwarded_for.split(",")]
        if ips:
            return ips[0]
    if "x-real-ip" in request.headers:
        return request.headers["x-real-ip"].strip()
    if request.client:
        return str(request.client.host)
    return "unknown"


async def refresh_provider_pings():
    while True:
        try:
            logger.info("Refreshing provider pings cache")
            output = LLMProviderStats.print_all_providers_info_html()
            PROVIDER_PING_CACHE["provider_infos_html"] = output
            logger.info(f"Provider pings cache updated: {len(output)} characters")            
        except Exception as e:
            logger.error(f"Error refreshing provider pings: {e}")
        await asyncio.sleep(1800)  # Refresh every 30 minutes



limiter = Limiter(key_func=get_client_ip)

@asynccontextmanager
async def lifespan(app: FastAPI):    
    logger.info("V2 Server starting up")
    tracemalloc.start()    
    app.state.thread_pool = ThreadPoolExecutor(
        max_workers=2,
        thread_name_prefix="PG-Writer"
    )
    app.state.last_updated = None
    app.state.total_requests = 0
    app.state.exceptions = 0
    #app.state.db = AsyncPGHelper()
    await initialize_database(
        username=config.DATABASE_USERNAME,
        password=config.DATABASE_PASSWORD,
        host=config.DATABASE_HOST,
        port=config.DATABASE_PORT,
        name=config.DATABASE_NAME
    )
    
    # Background task to restart manager if dead
    async def restart_manager():
        logger.info("Starting restart_manager task")
        while True:
            try:
                if not metagraph_manager._process or not metagraph_manager._process.is_alive():
                    logger.warning("Restarting dead MetagraphSyncManager process")
                    metagraph_manager.start()
                snapshot, _ = metagraph_manager.get_snapshot()
                metagraph_snapshot["nodes"] = snapshot
                logger.info(f"Metagraph snapshot updated with {len(snapshot)} nodes")
            except Exception as e:
                logger.error(f"Error in restart_manager: {e}")
            await asyncio.sleep(60)
    
    #metagraph_manager.start()
    #app.state.restart_task = asyncio.create_task(restart_manager())
    #app.state.refresh_task = asyncio.create_task(refresh_provider_pings())

    try:
        yield
    finally:
        logger.info("Starting shutdown...")
        app.state.restart_task.cancel()
        app.state.refresh_task.cancel()
        try:
            await app.state.restart_task
            await app.state.refresh_task
        except asyncio.CancelledError:
            pass        
        
        metagraph_manager.stop()
        await http_client.aclose()
        logger.info("Shutting down PG writer thread pool...")
        app.state.thread_pool.shutdown(wait=True, cancel_futures=False)
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

app = FastAPI(
    title=f"Bitrecs V2 Testnet",
    version=app_version,
    description=f"(Netuid: {BT_NETWORK} - Network: {BT_NETUID})",
    debug=False,
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


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


@app.get("/")
@limiter.limit("60/minute")
async def read_root(request: Request):
    ts = str(int(time.time()))
    request_ip = get_client_ip(request)
    logger.info(f"Root endpoint accessed from IP {request_ip} at {ts}")
    return JSONResponse(
        status_code=200,
        content={"message": "Bitrecs V2 Testnet",
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
    snapshot, synced_at = metagraph_manager.get_snapshot()
    node_count = len(snapshot)
    thread_count = threading.active_count()
    message = "OK"
    if thread_count > 10:
        message = "WARNING: High thread count"
        logger.warning(f"High thread count: {thread_count}")
        logger.warning("Active threads:")
        for thread in threading.enumerate():
            logger.warning(f"  - {thread.name} (daemon={thread.daemon}, alive={thread.is_alive()})")

    if thread_count > 50:
        message = "CRITICAL: Very high thread count"
        logger.error(f"CRITICAL: Thread count {thread_count}")            
    
    current, peak = tracemalloc.get_traced_memory()
    version_file = load_version_info()

    db_health = await check_database_health()
    db_status = "OK" if db_health else "ERROR"
    agent_count = await get_agent_count()
    return {
        "status": "healthy",
        "nodes": node_count,
        "db_status": db_status,
        "total_requests": app.state.total_requests,
        "exceptions": app.state.exceptions,
        "agent_count": agent_count,
        "threads": thread_count,
        "metagraph_last_synced": int(synced_at) if synced_at else None,
        "metagraph_age_seconds": round(time.time() - synced_at, 2) if synced_at else None,        
        "thread_pool_workers": len(app.state.thread_pool._threads) if hasattr(app.state.thread_pool, '_threads') else 0,
        "memory_current_mb": round(current / 1024 / 1024, 2),
        "memory_peak_mb": round(peak / 1024 / 1024, 2),        
        "message": message,
        "version": version_file.strip() if version_file else "N/A"
    }


@app.get("/public_key")
@limiter.limit("120/minute")
async def get_public_key(request: Request):
    client_ip = get_client_ip(request)
    logger.info(f"Public key requested from IP: {client_ip}")
    public_key_raw_bytes = PUBLIC_KEY.public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw
    )
    public_key_hex = public_key_raw_bytes.hex()
    return JSONResponse(status_code=200, content={"public_key": public_key_hex})


@app.get("/providers")
@limiter.limit("60/minute")
async def provider_log(request: Request):
    request_ip = get_client_ip(request)
    logger.info(f"providers endpoint accessed from IP {request_ip}")    
    cache_key = "provider_infos_html"
    if cache_key in PROVIDER_PING_CACHE:
        logger.info(f"providers endpoint accessed from IP {request_ip} - using cached data")
        infos = PROVIDER_PING_CACHE[cache_key]
        return HTMLResponse(content=infos)
    logging.warning("Cache Broken")
    return HTMLResponse(content="<pre>Cache Empty</pre>")


@app.get("/miners")
@limiter.limit("60/minute")
async def get_miners(request: Request):
    client_ip = get_client_ip(request)
    logger.info(f"Miners endpoint accessed from IP {client_ip}")
    snapshot, _ = metagraph_manager.get_snapshot()
    miners = [node for node in snapshot.values() if node.get("stake", 0) > 0]  # Rough filter for miners
    return JSONResponse(content={"miners": miners})


@app.get("/validators")
@limiter.limit("60/minute")
async def get_validators(request: Request):
    client_ip = get_client_ip(request)
    logger.info(f"Validators endpoint accessed from IP {client_ip}")
    snapshot, _ = metagraph_manager.get_snapshot()
    validators = [node for node in snapshot.values() if node.get("stake", 0) == 0]  # Rough filter for validators
    return JSONResponse(content={"validators": validators})


@app.get("/artifact")
@limiter.limit("60/minute")
async def get_artifact(request: Request, artifact_id: str):
    client_ip = get_client_ip(request)
    logger.info(f"Artifact endpoint accessed from IP {client_ip} for ID {artifact_id}")
    try:
        if not artifact_id or len(artifact_id.strip()) == 0:            
            return JSONResponse(content={"error": "Invalid artifact_id"}, status_code=400)
        artifact = {"id": artifact_id, "data": "placeholder"}
        return JSONResponse(content=artifact)

    except Exception as e:
        logger.error(f"Error fetching artifact {artifact_id}: {e}")
        return JSONResponse(content={}, status_code=500)
        

@app.get("/artifacts")
@limiter.limit("60/minute")
async def get_artifacts(request: Request, limit: int = 10):
    client_ip = get_client_ip(request)
    logger.info(f"Artifacts endpoint accessed from IP {client_ip}")
    try:
        top_agents = await get_agents_by_top_limit(limit)    
        logger.info(f"Returning {len(top_agents)} top agents")
        return JSONResponse(content={"artifacts": [agent.model_dump(mode="json") for agent in top_agents]})
    except Exception as e:
        logger.error(f"Error fetching top agents: {e}")
        return JSONResponse(content={"artifacts": []}, status_code=500)
    
  

@app.post("/artifact")
@limiter.limit("60/minute")
async def submit_artifact(request: Request, artifact: Dict[str, Any]):
    client_ip = get_client_ip(request)
    logger.info(f"Submit artifact endpoint accessed from IP {client_ip}")    
    try:        
        artifact_instance = Agent(**artifact)
        validated, reason = validate_artifact(artifact_instance)
        if not validated:
            logger.warning(reason)
            return JSONResponse(content={"error": reason}, status_code=400)
        
        artifact_instance.agent_id = uuid.uuid4()
        artifact_id = await create_agent(artifact_instance)        
        logger.info(f"Artifact submitted successfully with ID: {artifact_id}")
        return JSONResponse(status_code=201, content={
            "message": "Artifact submitted successfully",
            "artifact_id": str(artifact_id)
        })
    
    except Exception as e:
        logger.error(f"Error submitting artifact: {e}")
        return JSONResponse(content={"error": "Failed to submit artifact"}, status_code=400)



@app.get("/run")
@limiter.limit("60/minute")
async def get_run(request: Request, run_id: str):
    client_ip = get_client_ip(request)
    logger.info(f"Run endpoint accessed from IP {client_ip} for ID {run_id}")
    # Rough placeholder: return dummy run
    run = {"id": run_id, "data": "placeholder"}
    return JSONResponse(content=run)

@app.get("/runs")
@limiter.limit("60/minute")
async def get_runs(request: Request):
    client_ip = get_client_ip(request)
    logger.info(f"Runs endpoint accessed from IP {client_ip}")
    # Rough placeholder: return list of dummy runs
    runs = [{"id": f"run_{i}", "data": "placeholder"} for i in range(5)]
    return JSONResponse(content={"runs": runs})
