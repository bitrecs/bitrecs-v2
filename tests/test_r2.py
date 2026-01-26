import pytest
import os
import secrets
from utils.r2 import upload_text_file_to_r2, download_text_file_from_r2, validate_r2_bucket_connection

TEST_BUCKET = os.getenv("R2_BUCKET_NAME")
TEST_ACCESS_KEY = os.getenv("R2_ACCESS_KEY_ID")
TEST_SECRET_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
TEST_ENDPOINT = os.getenv("R2_ENDPOINT_URL")
TEST_PATH = "test-integration-file.txt"
TEST_TEXT = f"Integration test content! - {secrets.token_hex(8)}"


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

