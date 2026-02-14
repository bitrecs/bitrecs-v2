
import os
import json
import bittensor as bt
from models.miner_submission import MinerSubmission
from utils.gist import get_gist_hash, get_gist_sha_commits
import utils.logger as logger
from bittensor.core.errors import MetadataError
from typing import Optional
from utils.subtensor import get_subtensor
from utils.verify import verify_submission_signature

NETUID = int(os.getenv("NETUID", 296))


async def is_commitment_valid(submission: MinerSubmission) -> bool:
    """
    Validate a miner submission by checking the on-chain commitment and verifying the signature.    
    Each hotkey should have only one commitment, and the commitment data must match the submission data. 
    Finally, the signature must be valid for the preamble constructed from the submission.      

    Args:
        submission (MinerSubmission): The miner submission to validate
    Returns:
        bool: True if the submission is valid, False otherwise
    """
    try:

        if not verify_submission_signature(submission):
            logger.warning(f"Signature verification failed for hotkey {submission.hotkey}")
            return False
        
        sub = await get_subtensor()
        commitments = await sub.get_revealed_commitment_by_hotkey(
            netuid=NETUID,
            hotkey_ss58=submission.hotkey
        )
        if not commitments:
            logger.warning(f"No commitment found for hotkey {submission.hotkey}")
            return False
        if len(commitments) != 1:
            logger.warning(f"Multiple commitments found for hotkey {submission.hotkey}, expected only one")
            return False
        chain_commitment = commitments[0]
        parts = chain_commitment.split(":")
        if len(parts) != 2:
            logger.warning(f"Invalid commitment format for hotkey {submission.hotkey}")
            return False
        a = f"{parts[0]}:{parts[1]}"
        commit_sha = get_gist_sha_commits(submission.gist_id)[0]
        content_sha = get_gist_hash(submission.github_account, submission.gist_id)
        b = f"{commit_sha}:{content_sha}"      
        if a != b:
            logger.warning(f"Commitment data mismatch for hotkey {submission.hotkey}: expected {b}, got {a}")
            return False        
        return True    
    except Exception as e:
        logger.error(f"Error validating commitment: {e}")
        return False


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
    coldkey: str,
    hotkey: str
) -> bool:
    """Miner commitment to chain indicating their ownership of the Gist artifact.    
    Args:      
        gist_id (str): Gist ID containing the artifact.yaml        
        coldkey (str): Name of the coldkey in the wallet
        hotkey (str): Name of the hotkey in the wallet      
    """
   
    wallet = bt.Wallet(name=coldkey, hotkey=hotkey)
    
    logger.info(f"Committing ownership of Gist {gist_id} to chain")
    logger.info(f"Using wallet: {wallet.hotkey.ss58_address[:16]}...")

    commit_sha = get_gist_sha_commits(gist_id)[0]
    content_sha = get_gist_hash(github_account, gist_id)
    preamble = f"{commit_sha}:{content_sha}"    
   
    async def _commit():
        sub = await get_subtensor()
        data = preamble        
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
        
        print(f"Commited: {preamble} for hotkey {wallet.hotkey.ss58_address}")        
        logger.info("Commit successful")
        return True
    
    except Exception as e:
        logger.error(f"Commit failed: {e}")
        print(json.dumps({"success": False, "error": str(e)}))
        raise




# async def commit_to_chain2(
#     github_account: str,
#     gist_id: str,
#     created_at: str,
#     coldkey: str,
#     hotkey: str
# ) -> bool:
#     """Miner commitment to chain indicating their ownership of the Gist artifact. 
#     The commitment data includes the GitHub account, Gist ID, creation timestamp, and the miner's hotkey.

#     Args:
#         github_account (str): GitHub account name
#         gist_id (str): Gist ID containing the artifact.yaml
#         created_at (str): ISO formatted timestamp of when the Gist was created
#         coldkey (str): Name of the coldkey in the wallet
#         hotkey (str): Name of the hotkey in the wallet
      
#     """  
   
#     wallet = bt.Wallet(name=coldkey, hotkey=hotkey)
    
#     logger.info(f"Committing: {github_account}@{gist_id} (created_at: {created_at})")
#     logger.info(f"Using wallet: {wallet.hotkey.ss58_address[:16]}...")

#     preamble = f"{created_at}:{github_account}:{gist_id}:{wallet.hotkey.ss58_address}"    
#     signature = wallet.hotkey.sign(preamble).hex()
#     submission = MinerSubmission(
#         created_at=created_at,
#         github_account=github_account,
#         gist_id=gist_id,
#         hotkey=wallet.hotkey.ss58_address,      
#         signature=signature
#     )

#     async def _commit():
#         sub = await get_subtensor()
#         data = json.dumps(submission.to_dict())
        
#         while True:
#             try:
#                 await sub.set_reveal_commitment(
#                     wallet=wallet,
#                     netuid=NETUID,
#                     data=data,
#                     blocks_until_reveal=1
#                 )
#                 break
#             except MetadataError as e:
#                 if "SpaceLimitExceeded" in str(e):
#                     logger.warning("Space limit exceeded, waiting for next block...")
#                     await sub.wait_for_block()
#                 else:
#                     raise
    
#     try:
#         await _commit()
        
#         result = {
#             "success": True,
#             "created_at": created_at,
#             "github_account": github_account,
#             "gist_id": gist_id,
#             "hotkey": wallet.hotkey.ss58_address,
#             "signature": signature                        
#         }
#         print(json.dumps(result))
#         logger.info("Commit successful")
#         return True
    
#     except Exception as e:
#         logger.error(f"Commit failed: {e}")
#         print(json.dumps({"success": False, "error": str(e)}))
#         raise