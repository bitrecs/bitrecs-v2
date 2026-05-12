from typing import Optional
from utils.database import db_operation, DatabaseConnection
import utils.logger as logger

@db_operation
async def save_temp_key(conn: DatabaseConnection, hotkey: str, temp_key: str) -> bool:
    try:      
        await conn.execute(
            """
            INSERT INTO temp_keys (miner_hotkey, or_temp_key) VALUES ($1, $2)
            """,
            hotkey, temp_key
        )
        return True
    except Exception as e:
        logger.error(f"Error saving temporary key to database: {e}")
        return False
    
@db_operation
async def get_temp_key(conn: DatabaseConnection, hotkey: str) -> Optional[str]:
    try:
        row = await conn.fetchrow(
            """
            SELECT or_temp_key FROM temp_keys WHERE miner_hotkey = $1
            ORDER BY created_at DESC LIMIT 1;
            """,
            hotkey
        )
        if row:
            return row["or_temp_key"]
        return None
    except Exception as e:
        logger.error(f"Error retrieving temporary key from database: {e}")
        return None
    
@db_operation
async def delete_temp_key(conn: DatabaseConnection, hotkey: str) -> bool:
    try:
        await conn.execute(
            """
            DELETE FROM temp_keys WHERE miner_hotkey = $1
            """,
            hotkey
        )
        return True
    except Exception as e:
        logger.error(f"Error deleting temporary key from database: {e}")
        return False