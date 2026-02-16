import re
from bittensor.core.async_subtensor import AsyncSubtensor
from bittensor_wallet.keypair import Keypair

import api.config as config
import utils.logger as logger


async def check_if_hotkey_is_registered(hotkey: str) -> bool:
    subtensor = AsyncSubtensor(network=config.SUBTENSOR_NETWORK)
    return await subtensor.is_hotkey_registered(hotkey_ss58=hotkey, netuid=config.NETUID)

# def validate_signed_timestamp(timestamp: int, signed_timestamp: str, hotkey: str) -> bool:
#     try:
#         keypair = Keypair(ss58_address=hotkey)
#         return keypair.verify(str(timestamp), bytes.fromhex(signed_timestamp))
#     except Exception as e:
#         logger.warning(f"Error in validate_signed_timestamp(timestamp={timestamp}, signed_timestamp={signed_timestamp}, hotkey={hotkey}): {e}")
#         return False
    
    
def is_hotkey_valid_format(hotkey: str) -> bool:
    if not isinstance(hotkey, str) or len(hotkey) != 48:
        return False
    # regex s58 address
    pattern = r"^5[1-9A-HJ-NP-Za-km-z]{47}$"
    if re.match(pattern, hotkey):
        return True
    return False