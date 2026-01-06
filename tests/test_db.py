

def test_db_health():
    import asyncio
    from utils.database import check_database_health

    loop = asyncio.get_event_loop()
    is_healthy = loop.run_until_complete(check_database_health())
    assert is_healthy is True