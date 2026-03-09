import utils.logger as logger
from queries.hotkey_gist import get_hotkey_from_gist
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from api.config import MINER_AGENT_UPLOAD_RATE_LIMIT_SECONDS
from queries.banned_hotkey import get_banned_hotkey, is_hotkey_used
from utils.bittensor import check_if_hotkey_is_registered
from utils.validator_hotkeys import WHITELISTED_VALIDATORS

MAX_FILE_SIZE_MB = 1

async def check_if_hotkey_is_validator(hotkey: str) -> None:
    match = [w for w in WHITELISTED_VALIDATORS if w["hotkey"] == hotkey]
    if match:
        logger.error(f"A miner attempted to upload an agent with a hotkey that belongs to a whitelisted validator: {hotkey}.")
        raise HTTPException(
            status_code=400,
            detail="Hotkey belongs to a whitelisted validator and cannot be used for agent submission. Please register a new hotkey"
        )   


async def check_if_hotkey_used(hotkey: str) -> None:
    is_used = await is_hotkey_used(hotkey)
    if is_used:
        logger.error(f"A miner attempted to upload an agent with a hotkey that is already in use: {hotkey}.")
        raise HTTPException(
            status_code=400,
            detail="Hotkey has already been used for an agent submission. Please register a new hotkey"
        )
    
async def check_if_gist_used(gist: str) -> None:
    hotkey = await get_hotkey_from_gist(gist)
    if hotkey is not None:
        logger.error(f"A miner attempted to upload an agent with a gist that is already in use: {gist}.")
        raise HTTPException(
            status_code=400,
            detail="Gist has already been used for an agent submission. Please create a new gist"
        )


async def check_agent_banned(miner_hotkey: str) -> None:
    logger.debug(f"Checking if miner hotkey {miner_hotkey} is banned...")

    if await get_banned_hotkey(miner_hotkey) is not None:
        logger.error(f"A miner attempted to upload an agent with a banned hotkey: {miner_hotkey}.")
        raise HTTPException(
            status_code=403,
            detail="Your miner hotkey has been banned for attempting to obfuscate code or otherwise cheat. If this is in error, please contact us on Discord"
        )
    
    logger.debug(f"Miner hotkey {miner_hotkey} is not banned.")

def check_rate_limit(latest_agent_created_at_in_latest_set_id: datetime) -> None:
    logger.debug(f"Checking if miner is rate limited...")

    earliest_allowed_time = latest_agent_created_at_in_latest_set_id + timedelta(seconds=MINER_AGENT_UPLOAD_RATE_LIMIT_SECONDS)
    logger.debug(f"Earliest allowed time: {earliest_allowed_time}. Current time: {datetime.now(timezone.utc)}. Difference: {datetime.now(timezone.utc) - earliest_allowed_time}. Minimum allowed time: {timedelta(seconds=MINER_AGENT_UPLOAD_RATE_LIMIT_SECONDS)}.")
    
    if datetime.now(timezone.utc) < earliest_allowed_time:
        logger.error(f"A miner attempted to upload an agent too quickly. Latest agent created at {latest_agent_created_at_in_latest_set_id} and current time is {datetime.now(timezone.utc)}.")
        raise HTTPException(
            status_code=429,
            detail=f"You must wait {MINER_AGENT_UPLOAD_RATE_LIMIT_SECONDS} seconds before uploading a new agent version"
        )
    
    logger.debug(f"Miner is not rate limited.")


async def check_hotkey_registered(miner_hotkey: str) -> None:
    logger.debug(f"Checking if miner hotkey {miner_hotkey} is registered on subnet...")
    if not await check_if_hotkey_is_registered(miner_hotkey):
        logger.error(f"A miner attempted to upload an agent with a hotkey that is not registered on subnet: {miner_hotkey}.")
        raise HTTPException(status_code=400, detail=f"Hotkey not registered on subnet")    
    logger.debug(f"Miner hotkey {miner_hotkey} is registered on the subnet.")




