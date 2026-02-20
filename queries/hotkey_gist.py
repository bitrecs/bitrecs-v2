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



@db_operation
async def get_miner_first_blocks(conn: DatabaseConnection) -> dict[str, int]:
    rows = await conn.fetch(
        """
        SELECT miner_hotkey, MIN(block) as first_block 
        FROM hotkey_gist 
        WHERE block != 0
        GROUP BY miner_hotkey

        """
    )
    return {row['miner_hotkey']: row['first_block'] for row in rows}
    