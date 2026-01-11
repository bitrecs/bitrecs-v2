
import asyncio
from api import config
from api.endpoints.validator import delete_validators_that_have_not_sent_a_heartbeat
from utils import logger


async def validator_heartbeat_timeout_loop():
    logger.info("Starting validator heartbeat timeout loop...")

    while True:
        await delete_validators_that_have_not_sent_a_heartbeat()

        await asyncio.sleep(config.VALIDATOR_HEARTBEAT_TIMEOUT_INTERVAL_SECONDS)