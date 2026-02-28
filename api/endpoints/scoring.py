import api.config as config
import pandas as pd
from fastapi import APIRouter, Request
from datetime import datetime
from pydantic import BaseModel
from itertools import combinations
from typing import Any, Dict, Optional
from api.utils.limiter import limiter
from queries.scores import get_miner_scores
from utils.ttl import ttl_cache
from scoring.pareto import compute_pareto_frontier
from scoring.threshold import compute_miner_thresholds
from scoring.wta import compute_subset_scores_with_priority, find_subset_winner_with_priority, scores_to_weights
from scoring.engine import df_to_miner_blocks, df_to_miner_scores, df_to_samples, get_current_eval_set_id
from models.evaluation_set import EvaluationSetGroup
from queries.evaluation_set import get_latest_set_id, get_set_created_at
from queries.statistics import get_average_score_per_evaluation_set_group, get_average_wait_time_per_evaluation_set_group

router = APIRouter()

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


@router.get("/pareto")
@limiter.limit("60/minute")
async def pareto_frontier(request: Request) -> Dict[str, Any]:
    current_set_id = get_current_eval_set_id()
    print(f"Current evaluation_set_id: {current_set_id}") 
    data = await get_miner_scores(evaluation_set_id=current_set_id)
    miner_scores = df_to_miner_scores(data)
    samples = df_to_samples(data)
    envs = list(samples.keys())    
    pareto_result = compute_pareto_frontier(miner_scores=miner_scores, env_ids=envs, n_samples_per_env=samples)    
    # Aggregate dominance into stats
    dominance_df = pd.DataFrame({
        'uid': pareto_result.uid_mapping,
        'on_frontier': [uid in pareto_result.frontier_uids for uid in pareto_result.uid_mapping],
        'dominated_count': [sum(row) for row in pareto_result.dominance_matrix]
    })
    dominance_df['score_avg'] = [miner_scores.get(uid, {}).values() for uid in dominance_df['uid']]
    # Simplify score_avg to mean across envs
    dominance_df['score_avg'] = dominance_df['score_avg'].apply(lambda x: sum(x)/len(x) if x else 0)
    stats = dominance_df.sort_values('on_frontier', ascending=False).to_dict('records')
    
    # Summarized logs
    frontier_count = len(pareto_result.frontier_uids)
    print(f"Pareto Frontier: {frontier_count}/{len(pareto_result.uid_mapping)} UIDs on frontier")
    
    # Reduced output
    return {
        "frontier_uids": pareto_result.frontier_uids,
        "dominance_matrix": pareto_result.dominance_matrix.tolist()[:10],  # Limit rows
        "score_matrix": pareto_result.score_matrix.tolist()[:10],
        "uid_mapping": pareto_result.uid_mapping,
        "miner_scores": miner_scores,  # Keep or limit
        "samples": samples,
        "dominance_explanation": {uid: "On frontier" if uid in pareto_result.frontier_uids else f"Dominated by others" for uid in pareto_result.uid_mapping},
        "stats": stats,  # Aggregated table
    }


@router.get("/wta")
@limiter.limit("60/minute")
async def winner_take_all(request: Request) -> Dict[str, Any]:
    current_set_id = get_current_eval_set_id()
    print(f"Current evaluation_set_id: {current_set_id}")  
    data = await get_miner_scores(evaluation_set_id=current_set_id)
    miner_scores = df_to_miner_scores(data)
    samples = df_to_samples(data)
    envs = list(samples.keys())
    miner_blocks = df_to_miner_blocks(data)
    miner_thresholds = compute_miner_thresholds(miner_scores, episodes_per_env=samples)
    subset_scores = compute_subset_scores_with_priority(
        miner_scores, miner_thresholds, miner_blocks, envs
    )
    weights = scores_to_weights(subset_scores)
    
    # Aggregate subset winners into stats (using pandas)
    subset_winners = {
        str(subset): find_subset_winner_with_priority(miner_scores, miner_thresholds, miner_blocks, subset)
        for subset_size in range(1, len(envs) + 1)
        for subset in combinations(envs, subset_size)
    }
    winners_df = pd.DataFrame(list(subset_winners.items()), columns=['subset', 'winner_uid'])
    stats_df = winners_df.groupby('winner_uid').size().reset_index(name='subsets_won')
    stats_df['weight'] = stats_df['winner_uid'].map(weights).fillna(0.0)
    stats_df['rank'] = stats_df['weight'].rank(ascending=False, method='dense').astype(int)
    stats = stats_df.sort_values('weight', ascending=False).to_dict('records')  # List of dicts for JSON
    
    # Summarized logs (instead of per-subset)
    total_subsets = len(subset_winners)
    print(f"\nTotal subsets: {total_subsets}")
    for _, row in stats_df.iterrows():
        print(f"UID {row['winner_uid']}: {row['subsets_won']}/{total_subsets} subsets, weight {row['weight']:.4f}")
    
    # Reduced output (keep core, add stats, limit subset_winners to top 10)
    top_subset_winners = dict(list(subset_winners.items())[:10])  # First 10 as example
    return {
        "weights": weights,
        "subset_scores": subset_scores,
        "miner_thresholds": miner_thresholds,
        "miner_blocks": miner_blocks,
        "subset_winners": top_subset_winners,  # Limited
        "stats": stats,  # Aggregated table
    }