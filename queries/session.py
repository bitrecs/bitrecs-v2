import hashlib
from typing import Optional
from utils.database import db_operation, DatabaseConnection

@db_operation
async def insert_validator_session(conn: DatabaseConnection, session, name, hotkey, ip) -> Optional[int]:    
    try:
        sha_session = hashlib.sha256(str(session).encode()).hexdigest()
        result = await conn.fetchval("""
        INSERT INTO sessions (
            session_id,
            node_name,
            node_hotkey,
            ip_address        
        ) VALUES ($1, $2, $3, $4)
        RETURNING id
        """, sha_session, name, hotkey, ip)
        return result
    except Exception as e:
        print(f"Error inserting validator session: {e}")
        return -1
