import os
import httpx
import asyncio
import utils.logger as logger
import validator.config as config
from pathlib import Path
from utils.subtensor import close_subtensor, get_subtensor
from scoring.persist import ScorePersister
from scoring.threshold import compute_miner_thresholds
from scoring.types import MinerFirstBlocks, MinerScores
from scoring.wta import compute_subset_scores_with_priority, scores_to_weights


def get_current_eval_set_id() -> int:    
    platform_url = os.environ.get("RIDGES_PLATFORM_URL", "")
    client = httpx.Client(base_url=platform_url)
    response = client.get("/scoring/latest-set-info")
    result = response.json()
    logger.info(f"Latest evaluation set info: {result}")
    if response.status_code == 200 and "latest_set_id" in result:
        return result["latest_set_id"]
    else:        
        logger.error(f"Failed to retrieve latest evaluation set ID: {response.status_code} - {response.text}")
        raise Exception("Failed to retrieve latest evaluation set ID")
    

def df_to_miner_scores(df) -> MinerScores:
    miner_scores: MinerScores = {}
    for _, row in df.iterrows():
        uid = row['uid']
        env_id = row['task_name']
        score = row['score']        
        if uid not in miner_scores:
            miner_scores[uid] = {}
        miner_scores[uid][env_id] = score
    return miner_scores


def df_to_samples(df) -> dict[str, int]:
    samples = {}
    for _, row in df.iterrows():
        env_id = row['task_name']
        sample_size = row['sample_size']
        if env_id not in samples:
            samples[env_id] = 0
        samples[env_id] = sample_size
    return samples


def miners_first_blocks() -> MinerFirstBlocks:
    SERVICE_URL = os.environ.get("RIDGES_PLATFORM_URL", "")    
    client = httpx.Client(base_url=SERVICE_URL)
    response = client.get("/retrieval/miner-blocks")
    assert response.status_code == 200
    data = response.json()
    return data
    

def df_to_miner_blocks(df) -> MinerFirstBlocks:
    miner_blocks = miners_first_blocks()
    # miner blocks uses hotkey as key, but we want to map to uid, so we need to convert
    hotkey_to_uid = {}
    for _, row in df.iterrows():
        hotkey = row['hotkey']
        uid = row['uid']
        hotkey_to_uid[hotkey] = uid
    miner_first_blocks: MinerFirstBlocks = {}
    for hotkey, block in miner_blocks.items():
        uid = hotkey_to_uid.get(hotkey)
        if uid is not None:
            miner_first_blocks[uid] = block
    return miner_first_blocks


async def calculate_scores() -> bool:
    try:

        logger.info("Calculating scores...")
        current_set_id = get_current_eval_set_id()
        logger.info(f"Current evaluation set ID: {current_set_id}")
        
        root_path = Path(__file__).parent.parent.absolute()        
        persister = ScorePersister(base_path=root_path, filename="scores.db")
        data = persister.load_scores(evaluation_set_id=current_set_id)
        logger.info(f"Loaded {len(data)} score records")
        if data.empty:
            logger.warning("\033[33mNo score data available to process\033[0m")
            return False
        
        logger.info("Calculating miner scores and weights...")
        miner_scores = df_to_miner_scores(data)
        samples = df_to_samples(data)
        envs = list(samples.keys())
        miner_blocks = df_to_miner_blocks(data)
        miner_thresholds = compute_miner_thresholds(miner_scores, episodes_per_env=samples)
        subset_scores = compute_subset_scores_with_priority(
            miner_scores, miner_thresholds, miner_blocks, envs
        )
        weights = scores_to_weights(subset_scores)
        logger.info("\nSubset scores:")
        for uid, score in sorted(subset_scores.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  UID {uid}: {score:.1f} points")

        logger.info("\nFinal weights:")
        for uid, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  UID {uid}: {weight:.4f}")

        #update weights on chain
        weight_receiving_uid = max(weights, key=weights.get)
        subtensor = await get_subtensor()
        success, message = await subtensor.set_weights(
            wallet=config.VALIDATOR_WALLET,
            netuid=config.NETUID,
            uids=[weight_receiving_uid],
            weights=[1],
            wait_for_inclusion=True,
            wait_for_finalization=True
        )    
        logger.info(f"\nSet weight of UID {weight_receiving_uid} to 1 on chain: {'Success' if success else 'Failure'} - {message}")    
        logger.info("\033[32mScores / Weights Update Complete\033[0m")
        await close_subtensor()
        
        return success
    
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()        
        logger.error(f"Exception in calculate_scores: {e}\n{traceback_str}")        
        raise