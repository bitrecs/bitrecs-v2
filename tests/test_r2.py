import os
import random
import time
import httpx
import httpx
import pytest
import secrets
from bittensor_wallet import Wallet
from datetime import datetime, timezone
from models.validator_upload_request import ValidatorUploadRequest
from utils.r2 import (
    create_upload_request_message, put_r2_upload, 
    upload_file_to_r2, upload_text_file_to_r2, 
    download_text_file_from_r2, validate_r2_bucket_connection
)
from utils.validator_hotkeys import WHITELISTED_VALIDATORS

TEST_BUCKET = os.getenv("R2_BUCKET_NAME")
TEST_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
TEST_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
TEST_ENDPOINT = os.getenv("R2_ENDPOINT_URL")
TEST_PATH = "test-integration-file.txt"
TEST_TEXT = f"Integration test content! - {secrets.token_hex(8)}"


def get_random_key():
    c = random.choice(WHITELISTED_VALIDATORS)
    return c.get("hotkey")


@pytest.mark.asyncio
async def test_r2_connection_basic():
    result = await validate_r2_bucket_connection(
        TEST_BUCKET, 
        TEST_ACCESS_KEY, 
        TEST_SECRET_KEY, 
        TEST_ENDPOINT
    )
    assert result is True


@pytest.mark.asyncio
async def test_r2_upload_download_integration():
    """Integration test: Upload and download a real file to/from R2."""
    if not all([TEST_BUCKET, TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_ENDPOINT]):
        pytest.skip("R2 credentials not set in environment. Set R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL.")    
    # Upload the file
    await upload_text_file_to_r2(TEST_BUCKET, TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_ENDPOINT, TEST_PATH, TEST_TEXT)    
    # Download and verify
    downloaded_text = await download_text_file_from_r2(TEST_BUCKET, TEST_ACCESS_KEY, TEST_SECRET_KEY, TEST_ENDPOINT, TEST_PATH)    
    assert downloaded_text == TEST_TEXT


@pytest.mark.asyncio
async def test_r2_scores_backup():
    """Test backup of scores to R2."""
    from pathlib import Path
    root_path = Path(__file__).parent.parent.absolute()       
    db_path = root_path / "scores.db" 
    if not db_path.exists():
        pytest.skip("Scores DB not found. Run scoring engine at least once to generate scores.db for this test.")
    
    validator_key = get_random_key()
    upload_path = f"{validator_key}/scores.db"
    upload_success = await upload_file_to_r2(bucket="v2-testnet", 
                      access_key_id=TEST_ACCESS_KEY, 
                      secret_access_key=TEST_SECRET_KEY, 
                      endpoint_url=TEST_ENDPOINT, 
                      path=upload_path, 
                      file_content=db_path.read_bytes(), 
                      content_type="application/octet-stream")    
    assert upload_success is True   


def test_validator_backup_r2_signed_request():
    SERVICE_URL = "http://localhost:8000"
    
    MINER_WALLET_NAME = os.getenv("MINER_WALLET_NAME")
    MINER_WALLET_HOTKEY_NAME = os.getenv("MINER_WALLET_HOTKEY_NAME")
    wallet = Wallet(name=MINER_WALLET_NAME, hotkey=MINER_WALLET_HOTKEY_NAME)    
    report = ValidatorUploadRequest(
        created_at=datetime.now(timezone.utc).isoformat(),
        hotkey=wallet.hotkey.ss58_address,
        uid=10
    )    
    timestamp = int(time.time())
    message, nonce = create_upload_request_message(timestamp, report)
    signature = wallet.hotkey.sign(message).hex()
    report_dict = report.to_dict()
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-Signature': signature,
        'X-Timestamp': str(timestamp),
        'X-Nonce': nonce
    }

    with httpx.Client() as client:
        response = client.post(f"{SERVICE_URL}/backup/upload-request", json=report_dict, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "signed_url" in data
        upload_url = data["signed_url"]
        assert upload_url.startswith("https")

  
def test_validator_backup_r2_via_url():
    MINER_WALLET_NAME = os.getenv("MINER_WALLET_NAME")
    MINER_WALLET_HOTKEY_NAME = os.getenv("MINER_WALLET_HOTKEY_NAME")
    wallet = Wallet(name=MINER_WALLET_NAME, hotkey=MINER_WALLET_HOTKEY_NAME)    
    upload_request = ValidatorUploadRequest(
        created_at=datetime.now(timezone.utc).isoformat(),
        hotkey=wallet.hotkey.ss58_address,
        uid=10
    )
    uploaded = put_r2_upload(upload_request, wallet.hotkey) 
    assert uploaded is True