from bittensor_wallet import Keypair
from models.miner_submission import MinerSubmission

def verify_submission_signature(submission: MinerSubmission) -> bool:
    preamble = f"{submission.created_at}:{submission.github_account}:{submission.gist_id}:{submission.hotkey}"
    preamble_bytes = preamble.encode('utf-8')
    signature_bytes = bytes.fromhex(submission.signature)
    return Keypair(ss58_address=submission.hotkey).verify(preamble_bytes, signature_bytes)
