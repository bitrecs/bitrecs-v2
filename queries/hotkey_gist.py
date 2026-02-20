from typing import Optional
from utils.database import db_operation, DatabaseConnection

@db_operation
async def log_hotkey_gist(conn: DatabaseConnection, hotkey: str, gist: str, block: int) -> None:
    result = await conn.fetchrow(
        """
        INSERT INTO hotkey_gist (miner_hotkey, gist, block) VALUES ($1, $2, $3)
        """,
        hotkey, gist, block
    )


@db_operation
async def get_hotkey_from_gist(conn: DatabaseConnection, gist: str) -> Optional[str]:
    hotkey = await conn.fetchrow(
        """
        SELECT miner_hotkey FROM hotkey_gist WHERE gist = $1
        """,
        gist      
    )
    if not hotkey:
        return None
    return hotkey[0]


