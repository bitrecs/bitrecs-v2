import pytest
import secrets
from queries.system_enabled import get_system_enabled
from utils.database import check_database_health
from queries.session import insert_validator_session

@pytest.mark.asyncio
@pytest.mark.usefixtures("db_setup")
async def test_db_health():
    is_healthy = await check_database_health()
    assert is_healthy is True


@pytest.mark.asyncio
@pytest.mark.usefixtures("db_setup")
async def test_insert_session():
    session_id = secrets.token_hex(8)
    name = "test_node"
    hotkey = "test_hotkey"
    ip = "127.0.0.1"
    inserted_session_id = await insert_validator_session(session_id, name, hotkey, ip)
    assert inserted_session_id > 0
    

@pytest.mark.asyncio
@pytest.mark.usefixtures("db_setup")
async def test_is_system_enabled():
    enabled = await get_system_enabled()
    print(f"System enabled status: {enabled}")
    assert isinstance(enabled, bool), "Expected a boolean value for system enabled status"

