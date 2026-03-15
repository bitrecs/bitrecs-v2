import os
import httpx
import asyncio
import utils.logger as logger
from bittensor_wallet import Keypair, Wallet
from utils.subtensor import close_subtensor, get_subtensor
from scoring.persist import ScorePersister
from scoring.threshold import compute_miner_thresholds
from scoring.types import MinerFirstBlocks, MinerScores
from scoring.wta import compute_subset_scores_with_priority, scores_to_weights
from queries.evaluation_set import get_latest_set_id
from scoring.constants import DEFAULT_Z_SCORE, MIN_THRESHOLD_GAP, MAX_THRESHOLD_GAP, MINER_EMISSION_PORTION


async def get_current_eval_set_id() -> int:
    try:
        return await get_latest_set_id()
    except Exception as e:
        SERVICE_URL = os.environ.get("BITRECS_PLATFORM_URL", "")    
        if not SERVICE_URL:
            SERVICE_URL = "http://localhost:8000"        
        headers = {"Content-Type": "application/json", 
                   "X-API-Key": os.environ.get("BITRECS_PLATFORM_API_KEY")}
        client = httpx.Client(base_url=SERVICE_URL, headers=headers)
        response = client.get("/scoring/latest-set-info")
        data = response.json()
        return data["latest_set_id"]
    

def df_to_miner_scores(df) -> MinerScores:
    """
    Aggregate scores across multiple validators per uid+task.    
    """
    miner_scores: MinerScores = {}
    grouped = df.groupby(['uid', 'task_name'])['score'].mean().reset_index()    
    for _, row in grouped.iterrows():
        uid = row['uid']
        env_id = row['task_name']
        score = row['score']
        if uid not in miner_scores:
            miner_scores[uid] = {}
        miner_scores[uid][env_id] = score    
    logger.info(f"Aggregated scores: {len(grouped)} uid+task combinations (mean across validators)")
    return miner_scores


def df_to_samples(df) -> dict[str, int]:
    """
    Get sample size per task
    """
    samples = {}    
    grouped = df.groupby('task_name')['sample_size'].max().reset_index()
    for _, row in grouped.iterrows():
        samples[row['task_name']] = row['sample_size']
    return samples


def miners_first_blocks() -> MinerFirstBlocks:
    SERVICE_URL = os.environ.get("BITRECS_PLATFORM_URL", "")    
    if not SERVICE_URL:
        SERVICE_URL = "http://localhost:8000"  
    headers = {"Content-Type": "application/json", 
            "X-API-Key": os.environ.get("BITRECS_PLATFORM_API_KEY")}
    client = httpx.Client(base_url=SERVICE_URL, headers=headers)
    response = client.get("/retrieval/miner-blocks")
    assert response.status_code == 200
    data = response.json()
    return data
    

def df_to_miner_blocks(df) -> MinerFirstBlocks:
    miner_blocks = miners_first_blocks()    
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


async def calculate_scores(netuid: int, validator_hotkey: Keypair, set_weights: bool = False) -> bool:
    try:
        logger.info("Calculating scores...")
        current_set_id = await get_current_eval_set_id()
        logger.info(f"Current evaluation set ID: {current_set_id}")        
        persister = ScorePersister(base_path="data/weights", filename="scores.db")
        data = persister.load_scores(evaluation_set_id=current_set_id)
        logger.info(f"Loaded {len(data)} score records")
        if data.empty:
            logger.warning(f"\033[33mNo score data available to process for evaluation set {current_set_id}\033[0m")
            return False
        
        logger.info("Calculating miner scores and weights...")
        miner_scores = df_to_miner_scores(data)
        samples = df_to_samples(data)
        envs = list(samples.keys())
        miner_blocks = df_to_miner_blocks(data)
        miner_thresholds = compute_miner_thresholds(miner_scores, episodes_per_env=samples,
                                                    z_score=DEFAULT_Z_SCORE,
                                                    min_gap=MIN_THRESHOLD_GAP,
                                                    max_gap=MAX_THRESHOLD_GAP)
        subset_scores = compute_subset_scores_with_priority(
            miner_scores, miner_thresholds, miner_blocks, envs
        )
        weights = scores_to_weights(subset_scores)
        logger.info("Subset scores:")
        for uid, score in sorted(subset_scores.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  UID {uid}: {score:.1f} points")

        logger.info("Final weights:")
        for uid, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  UID {uid}: {weight:.4f}")
        
        weight_receiving_uid = max(weights, key=weights.get)
        if set_weights:
            result = await set_weights_onchain(validator_hotkey, netuid, weight_receiving_uid)
            if result:
                logger.info(f"\033[32mWeights set successfully on chain for UID {weight_receiving_uid}\033[0m")
                return True
            else:
                logger.error(f"\033[31mFailed to set weights on chain for UID {weight_receiving_uid}\033[0m")
                return False            
        else:
            logger.info(f"\033[33mWeight candidate with highest score: {weight_receiving_uid}\033[0m")
            logger.info("\033[33mWeights not set on chain (set_weights=False)\033[0m")
            return False
    except asyncio.TimeoutError as te:
        logger.error(f"TimeoutError in calculate_scores: {te}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
    except Exception as e:
        logger.error(f"Exception in calculate_scores: {e}")
        import traceback
        traceback_str = traceback.format_exc()        
        logger.error(f"Full traceback: {traceback_str}")        
        raise


async def set_weights_onchain(validator_hotkey: Keypair, netuid: int, weight_receiving_uid: int) -> bool:
    wallet = Wallet(name=os.getenv("VALIDATOR_WALLET_NAME"), hotkey=os.getenv("VALIDATOR_HOTKEY_NAME"))
    if wallet.hotkey.ss58_address != validator_hotkey.ss58_address:
        logger.error(f"Validator hotkey mismatch: expected {wallet.hotkey.ss58_address}, got {validator_hotkey.ss58_address}")
        return False
    
    miner_weight = 1 * MINER_EMISSION_PORTION
    burn_weight = 1 - miner_weight
    if not (0 <= miner_weight <= 1):
        logger.error(f"Invalid weights: miner_weight={miner_weight}, burn_weight={burn_weight}. Must be >=0, <=1, and sum to 1.")
        return False
    
    uids = [0, weight_receiving_uid]
    weights = [burn_weight, miner_weight]    
    subtensor = await get_subtensor()
    try:
        max_retries = 3
        timeout = 90.0
        for attempt in range(max_retries):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_retries}")
                current_block = await subtensor.get_current_block()
                logger.info(f"Current block: {current_block}")
                success = await asyncio.wait_for(
                    subtensor.set_weights(
                        wallet=wallet,
                        netuid=netuid,
                        uids=uids,
                        weights=weights,
                        wait_for_inclusion=True,
                        wait_for_finalization=True,
                    ),
                    timeout=timeout
                )
                await post_weights_to_agora(wallet.hotkey.ss58_address, 
                                            current_block, uids, weights, 
                                            "ok" if success else "error")
                if success:
                    logger.info("✅ Weights set successfully (chain confirmed)")
                    return True
                else:
                    logger.error(f"❌ Chain rejected weight setting on attempt {attempt + 1}")
            except asyncio.TimeoutError:
                logger.error(f"Timeout on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1:
                logger.info("Retrying in 60 seconds...")
                await asyncio.sleep(60)
            else:
                logger.error("❌ All attempts failed")
                return False
        
        return False
    
    finally:
        await close_subtensor()


async def post_weights_to_agora(hotkey: str, block: int, uids: list[int], weights: list[float], status: str) -> None:
    logger.info(f"Posting weights to Agora: hotkey={hotkey}, block={block}, uids={uids}, weights={weights}, status={status}")
    return

    try:
        from utils.agora import post_to_agora, AgoraStatus
        weight_info = {f"uid{uid}": weight for uid, weight in zip(uids, weights)}
        payload = AgoraStatus(
            id="validator",
            from_server=hotkey,
            priority=1,
            description=str({"block": block, "weights": weight_info}),
            status=status
        )
        await post_to_agora(payload)
    except Exception as e:
        logger.error(f"post_weights_to_agora failed to post weights to Agora: {e}")
   