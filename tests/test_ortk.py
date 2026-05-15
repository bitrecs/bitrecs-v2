import os
import pytest
from utils.orkp import create_temporary_openrouter_key, validate_openrouter_key
from queries.temp_key import save_temp_key, get_temp_key, delete_temp_key
from dotenv import load_dotenv
load_dotenv()


@pytest.mark.asyncio
async def test_can_create_or_temp_key():    
    mgmt_key = os.getenv("OPENROUTER_MGMT_KEY")
    assert mgmt_key is not None, "OPENROUTER_MGMT_KEY environment variable must be set for this test"    
    temp_key = await create_temporary_openrouter_key(mgmt_key, name="test-temp-key", credit_limit_usd=0.10, expires_in_hours=1)
    assert temp_key is not None, "Failed to create temporary OpenRouter key"
    validated = await validate_openrouter_key(temp_key, model="mistralai/mistral-nemo")
    assert validated, "Created OpenRouter key failed validation"


@pytest.mark.asyncio
@pytest.mark.usefixtures("db_setup")
async def test_save_temp_key():    
    hotkey = "test_hotkey"
    temp_key = "test_temp_key_value"    
    save_result = await save_temp_key(hotkey, temp_key)
    assert save_result is True, "Expected save_temp_key to return True on successful save"


@pytest.mark.asyncio
@pytest.mark.usefixtures("db_setup")
async def test_get_temp_key():
    hotkey = "test_hotkey"
    temp_key = "test_temp_key_value"    
    await save_temp_key(hotkey, temp_key)
    retrieved_key = await get_temp_key(hotkey)
    assert retrieved_key == temp_key, "Expected get_temp_key to return the saved temporary key"


@pytest.mark.asyncio
@pytest.mark.usefixtures("db_setup")
async def test_delete_temp_key():    
    hotkey = "test_hotkey"
    temp_key = "test_temp_key_value"    
    await save_temp_key(hotkey, temp_key)
    delete_result = await delete_temp_key(hotkey)
    assert delete_result is True, "Expected delete_temp_key to return True on successful deletion"
    retrieved_key_after_delete = await get_temp_key(hotkey)
    assert retrieved_key_after_delete is None, "Expected get_temp_key to return None after deletion"