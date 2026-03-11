import time
import utils.logger as logger
from bittensor_wallet import Keypair, Wallet
from models.miner_submission import MinerSubmission

def validate_signed_timestamp(timestamp: int, signed_timestamp: str, hotkey: str) -> bool:
    try:
        keypair = Keypair(ss58_address=hotkey)
        return keypair.verify(str(timestamp), bytes.fromhex(signed_timestamp))
    except Exception as e:
        logger.warning(f"Error in validate_signed_timestamp(timestamp={timestamp}, signed_timestamp={signed_timestamp}, hotkey={hotkey}): {e}")
        return False

def verify_submission_signature(submission: MinerSubmission) -> bool:
    preamble = f"{submission.created_at}:{submission.github_account}:{submission.gist_id}:{submission.hotkey}"
    preamble_bytes = preamble.encode('utf-8')
    signature_bytes = bytes.fromhex(submission.signature)
    return Keypair(ss58_address=submission.hotkey).verify(preamble_bytes, signature_bytes)

def create_transport_signature(wallet: Wallet, submission: MinerSubmission, nonce: str) -> str:
    preamble = f"{submission.created_at}:{submission.github_account}:{submission.gist_id}:{submission.hotkey}:{nonce}"
    preamble_bytes = preamble.encode('utf-8')
    return wallet.hotkey.sign(preamble_bytes).hex()

def verify_transport_signature(submission: MinerSubmission, transport_signature: str, nonce: str) -> bool:
    submission_preamble = f"{submission.created_at}:{submission.github_account}:{submission.gist_id}:{submission.hotkey}:{nonce}"
    submission_preamble_bytes = submission_preamble.encode('utf-8')
    transport_signature_bytes = bytes.fromhex(transport_signature)
    return Keypair(ss58_address=submission.hotkey).verify(submission_preamble_bytes, transport_signature_bytes)
    
def verify_timestamp(timestamp: str, allowed_drift_seconds: int = 300) -> bool:
    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False    
    current_time = int(time.time())
    return abs(current_time - timestamp_int) <= allowed_drift_seconds