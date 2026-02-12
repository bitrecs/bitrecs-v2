import os
import json
import httpx
import pickle
from typing import Tuple

import yaml
from models.agent import Agent
from bittensor_wallet import Wallet
from bittensor.extras import timelock
from datetime import datetime, timezone
from rules.agent_validator import validate_artifact_template
from utils.gist import get_gist, get_gist_created_at
from dotenv import load_dotenv
load_dotenv()


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

GITHUB_ACCOUNT = "janusdotai"
GIST_ID = "dfbcc6e1abdaaa365ab4ce6b7e6d785c"

MINER_WALLET_NAME = os.getenv('MINER_WALLET_NAME')
MINER_WALLET_HOTKEY_NAME = "default"
MINER_WALLET_HOTKEY = os.getenv('MINER_WALLET_HOTKEY')
MINER_WALLET = Wallet(MINER_WALLET_NAME, MINER_WALLET_HOTKEY_NAME)


def timelock_encrypt(data: str, block_duration: int) -> Tuple[bytes, int]:
    """Encrypt data using timelock encryption."""
    encrypted_data, block = timelock.encrypt(data.encode('utf-8'), block_duration)
    return encrypted_data, block

def timelock_decrypt(encrypted_data: bytes) -> str:
    """Decrypt data using timelock decryption."""
    decrypted_data = timelock.wait_reveal_and_decrypt(encrypted_data, return_str=True)
    return decrypted_data


def test_download_gist():
    raw_url = f"https://gist.githubusercontent.com/{GITHUB_ACCOUNT}/{GIST_ID}/raw"
    with httpx.Client(follow_redirects=True) as client:
        response = client.get(raw_url, timeout=15.0)
        if response.status_code == 200:
            content = response.text
            save_path = os.path.join(CURRENT_DIR, "artifact.yaml")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("Downloaded artifact.yaml successfully")
            artifact = Agent.from_path(save_path)
            validated, reason = validate_artifact_template(artifact)
            assert validated, f"Artifact validation failed: {reason}"
        else:
            print(f"Failed: {response.status_code} - {response.reason_phrase}")

    if os.path.exists(save_path):
        os.remove(save_path)


def test_gist_created_at():
    created_at = get_gist_created_at(GIST_ID)
    print(f"Gist created at: {created_at.isoformat()}")
    assert isinstance(created_at, datetime), "created_at should be a datetime object"
    second_diff = (datetime.now(timezone.utc) - created_at).total_seconds()
    print(f"Gist age in seconds: {second_diff}")
    assert second_diff > 0, "Gist should be created in the past"
    minute_diff = second_diff / 60
    print(f"Gist age in minutes: {minute_diff}")
    hour_diff = minute_diff / 60
    print(f"Gist age in hours: {hour_diff}")


async def test_timelock_encrypt():
    data = "This is a test string for timelock encryption."
    n_blocks = 1
    encrypted_data, reveal_round = timelock_encrypt(data, n_blocks)    
    print(f"Encrypted data (hex): {encrypted_data.hex()}")
    print(f"Reveal round: {reveal_round}")
    assert isinstance(encrypted_data, bytes), "Encrypted data should be bytes"    

    decrypted_data = timelock_decrypt(encrypted_data)
    print(f"Decrypted data: {decrypted_data}")    
    assert decrypted_data == data, "Decrypted data should match the original data"


def test_miner_submission_dataclass():
    from models.miner_submission import MinerSubmission
    submission = MinerSubmission(
        created_at=datetime.now(timezone.utc).isoformat(),
        github_account=GITHUB_ACCOUNT,
        gist_id=GIST_ID,
        hotkey=MINER_WALLET_HOTKEY,        
        signature="test_signature"
    )
    print(submission)
    assert submission.github_account == GITHUB_ACCOUNT
    assert submission.gist_id == GIST_ID
    assert submission.hotkey == MINER_WALLET_HOTKEY

    byte_data = pickle.dumps(submission)
    n_blocks = 1
    encrypted, reveal_round = timelock.encrypt(byte_data, n_blocks)
    print(f"Encrypted submission (hex): {encrypted.hex()}")
    decrypted_bytes = timelock.wait_reveal_and_decrypt(encrypted)
    decrypted_submission = pickle.loads(decrypted_bytes)
    print(f"Decrypted submission: {decrypted_submission}")
    assert decrypted_submission == submission, "Decrypted submission should match the original submission"


def test_miner_submission_e2e():    
    # Step 1: Download and validate artifact from GIST
    gist_created_at = get_gist_created_at(GIST_ID)
    gist_raw_data = get_gist(GITHUB_ACCOUNT, GIST_ID)   
    artifact = Agent.from_yaml(gist_raw_data)
    validated, reason = validate_artifact_template(artifact)
    assert validated, f"Artifact validation failed: {reason}"
    
    # Step 2: Create MinerSubmission instance with signature
    preamble = f"{gist_created_at.isoformat()}:{GITHUB_ACCOUNT}:{GIST_ID}:{MINER_WALLET_HOTKEY}"
    print(f"Data to be signed: {preamble}")
    signature = MINER_WALLET.hotkey.sign(preamble).hex()
    print(f"Generated signature: {signature}")
    
    from models.miner_submission import MinerSubmission
    submission = MinerSubmission(
        created_at=gist_created_at.isoformat(),
        github_account=GITHUB_ACCOUNT,
        gist_id=GIST_ID,
        hotkey=MINER_WALLET_HOTKEY,      
        signature=signature
    )
    print(submission)
    assert submission.created_at == gist_created_at.isoformat()
    assert submission.github_account == GITHUB_ACCOUNT
    assert submission.gist_id == GIST_ID
    assert submission.hotkey == MINER_WALLET_HOTKEY
    assert submission.signature == signature

    byte_data = pickle.dumps(submission)
    n_blocks = 1
    encrypted, reveal_round = timelock.encrypt(byte_data, n_blocks)
    print(f"Encrypted submission (hex): {encrypted.hex()}")
    decrypted_bytes = timelock.wait_reveal_and_decrypt(encrypted)
    decrypted_submission = pickle.loads(decrypted_bytes)
    print(f"Decrypted submission: {decrypted_submission}")
    assert decrypted_submission == submission, "Decrypted submission should match the original submission"



    

