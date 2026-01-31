import time
import utils.logger as logger
from fastapi import APIRouter, Request
from utils.subtensor import get_subtensor
from utils.ttl import ttl_cache
from api.utils.limiter import limiter

from api.snapshot import metagraph_snapshot

router = APIRouter()

# /metagraph/info
@router.get("/info")
@limiter.limit("60/minute")
#@ttl_cache(ttl_seconds=15) # 15 seconds
async def info(request: Request):
    #st = await get_subtensor()    
    #current_block = await st.get_current_block()     

    logger.debug(f"Metagraph snapshot contains {len(metagraph_snapshot['nodes'])} nodes")
    logger.debug(f"{metagraph_snapshot}")     
    for hotkey, node_info in metagraph_snapshot["nodes"].items():
        logger.debug(f"Node {hotkey}: {node_info}")

    if not metagraph_snapshot["nodes"]:
        return {"error": "Metagraph data not yet available", "timestamp": int(time.time())}

    return {
        "nodes": metagraph_snapshot["nodes"],
        "timestamp": int(time.time())
    }

