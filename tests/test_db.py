import pytest
from utils.database import check_database_health

@pytest.mark.asyncio
@pytest.mark.usefixtures("db_setup")
async def test_db_health():
    is_healthy = await check_database_health()
    assert is_healthy is True