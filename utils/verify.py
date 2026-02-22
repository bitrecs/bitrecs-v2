import time
from bittensor_wallet import Keypair
from models.miner_submission import MinerSubmission

def verify_submission_signature(submission: MinerSubmission) -> bool:
    preamble = f"{submission.created_at}:{submission.github_account}:{submission.gist_id}:{submission.hotkey}"
    preamble_bytes = preamble.encode('utf-8')
    signature_bytes = bytes.fromhex(submission.signature)
    return Keypair(ss58_address=submission.hotkey).verify(preamble_bytes, signature_bytes)

def verify_transport_signature(submission: MinerSubmission, transport_signature: str, payment_block_hash: str, payment_extrinsic_hash: str, payment_extrinsic_index: int, nonce: str) -> bool:
    submission_preamble = f"{submission.created_at}:{submission.github_account}:{submission.gist_id}:{submission.hotkey}:{payment_block_hash}:{payment_extrinsic_hash}:{payment_extrinsic_index}:{nonce}"
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