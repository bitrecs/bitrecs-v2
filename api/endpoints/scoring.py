import api.config as config
from fastapi import APIRouter, Request
from datetime import datetime
from pydantic import BaseModel
from utils.ttl import ttl_cache
from typing import Optional
from models.evaluation_set import EvaluationSetGroup
from queries.evaluation_set import get_latest_set_id, get_set_created_at
from queries.statistics import get_average_score_per_evaluation_set_group, get_average_wait_time_per_evaluation_set_group
from api.utils.limiter import limiter

router = APIRouter()

# /scoring/weights
# @router.get("/weights")
# @limiter.limit("60/minute")
# async def weights(request: Request) -> Dict[str, float]:
#     if config.BURN:
#         return {config.OWNER_HOTKEY: 1.0}

#     # Try to get the weight-receiving agent's hotkey 
#     weight_receiving_agent_info = await get_weight_receiving_agent_info()
#     if weight_receiving_agent_info and "miner_hotkey" in weight_receiving_agent_info:
#         weight_receiving_hotkey = weight_receiving_agent_info["miner_hotkey"]
#         if await check_if_hotkey_is_registered(weight_receiving_hotkey):
#             return {weight_receiving_hotkey: 1.0}
#         else:
#             # Log a warning if the hotkey is not registered.            
#             logger.warning(f"Weight-receiving hotkey {weight_receiving_hotkey} is not registered on subnet {config.NETUID}.")
    
#     return {config.OWNER_HOTKEY: 1.0}


# /scoring/screener-info
class ScoringScreenerInfoResponse(BaseModel):
    screener_1_threshold: float
    screener_2_threshold: float
    prune_threshold: float

    screener_1_average_score: Optional[float] = None
    screener_2_average_score: Optional[float] = None
    validator_average_score: Optional[float] = None

    screener_1_average_wait_time: Optional[float] = None
    screener_2_average_wait_time: Optional[float] = None
    validator_average_wait_time: Optional[float] = None


@router.get("/screener-info")
@ttl_cache(ttl_seconds=60) # 1 minute
@limiter.limit("60/minute")
async def screener_info(request: Request) -> ScoringScreenerInfoResponse:
    average_score_per_evaluation_set_group = await get_average_score_per_evaluation_set_group()
    average_wait_time_per_evaluation_set_group = await get_average_wait_time_per_evaluation_set_group()

    return ScoringScreenerInfoResponse(
        screener_1_threshold=config.SCREENER_1_THRESHOLD,
        screener_2_threshold=config.SCREENER_2_THRESHOLD,
        prune_threshold=config.PRUNE_THRESHOLD,

        screener_1_average_score=average_score_per_evaluation_set_group[EvaluationSetGroup.screener_1],
        screener_2_average_score=average_score_per_evaluation_set_group[EvaluationSetGroup.screener_2],
        validator_average_score=average_score_per_evaluation_set_group[EvaluationSetGroup.validator],

        screener_1_average_wait_time=average_wait_time_per_evaluation_set_group[EvaluationSetGroup.screener_1],
        screener_2_average_wait_time=average_wait_time_per_evaluation_set_group[EvaluationSetGroup.screener_2],
        validator_average_wait_time=average_wait_time_per_evaluation_set_group[EvaluationSetGroup.validator]
    )



# /scoring/latest-set-info
class ScoringLatestSetInfo(BaseModel):
    latest_set_id: int
    latest_set_created_at: datetime

@router.get("/latest-set-info")
@limiter.limit("60/minute")
async def latest_set_info(request: Request) -> ScoringLatestSetInfo:
    latest_set_id = await get_latest_set_id()
    latest_set_created_at = await get_set_created_at(latest_set_id)
    return ScoringLatestSetInfo(
        latest_set_id=latest_set_id,
        latest_set_created_at=latest_set_created_at    
    )