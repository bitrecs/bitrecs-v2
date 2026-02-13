
import os
import json
import bittensor as bt
from models.miner_submission import MinerSubmission
import utils.logger as logger
from bittensor.core.errors import MetadataError
from typing import Optional
from utils.subtensor import get_subtensor

NETUID = int(os.getenv("NETUID", 296))


async def get_miner_commitments(hotkey_ss58: str) -> Optional[list]:
    try:
        sub = await get_subtensor()
        commitments = await sub.get_revealed_commitment_by_hotkey(netuid=NETUID, hotkey_ss58=hotkey_ss58)
        return commitments
    except Exception as e:
        logger.error(f"Error fetching miner commitments: {e}")
        return None
    


async def commit_to_chain(
    github_account: str,
    gist_id: str,
    created_at: str,
    coldkey: str,
    hotkey: str
) -> bool:
    """Miner commitment to chain

    Args:
        github_account (str): GitHub account name
        gist_id (str): Gist ID containing the artifact.yaml
        created_at (str): ISO formatted timestamp of when the Gist was created
        coldkey (str): Name of the coldkey in the wallet
        hotkey (str): Name of the hotkey in the wallet
      
    """  

    # cold = coldkey or get_conf("BT_WALLET_COLD", "default")
    # hot = hotkey or get_conf("BT_WALLET_HOT", "default")
    wallet = bt.Wallet(name=coldkey, hotkey=hotkey)
    
    logger.info(f"Committing: {github_account}@{gist_id} (created_at: {created_at})")
    logger.info(f"Using wallet: {wallet.hotkey.ss58_address[:16]}...")

    preamble = f"{created_at}:{github_account}:{gist_id}:{wallet.hotkey.ss58_address}"
    print(f"Data to be signed: {preamble}")
    signature = wallet.hotkey.sign(preamble).hex()

    submission = MinerSubmission(
        created_at=created_at,
        github_account=github_account,
        gist_id=gist_id,
        hotkey=wallet.hotkey.ss58_address,      
        signature=signature
    )

    async def _commit():
        sub = await get_subtensor()
        data = json.dumps(submission.to_dict())
        
        while True:
            try:
                await sub.set_reveal_commitment(
                    wallet=wallet,
                    netuid=NETUID,
                    data=data,
                    blocks_until_reveal=1
                )
                break
            except MetadataError as e:
                if "SpaceLimitExceeded" in str(e):
                    logger.warning("Space limit exceeded, waiting for next block...")
                    await sub.wait_for_block()
                else:
                    raise
    
    try:
        await _commit()
        
        result = {
            "success": True,
            "created_at": created_at,
            "github_account": github_account,
            "gist_id": gist_id,
            "hotkey": wallet.hotkey.ss58_address,
            "signature": signature                        
        }
        print(json.dumps(result))
        logger.info("Commit successful")
        return True
    
    except Exception as e:
        logger.error(f"Commit failed: {e}")
        print(json.dumps({"success": False, "error": str(e)}))
        raise
