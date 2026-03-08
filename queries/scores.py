import pandas as pd
from typing import Optional, Dict
from utils.database import db_operation, DatabaseConnection

@db_operation
async def get_miner_scores(conn: DatabaseConnection, evaluation_set_id: int) -> pd.DataFrame:
    query = """
    SELECT 
        run_id, uid, hotkey, task_name, score, success, duration, created_at, evaluation_set_id, sample_size
    FROM 
        miner_scores
    WHERE 
        evaluation_set_id = $1
    """
    rows = await conn.fetch(query, evaluation_set_id)
    if not rows:
        return pd.DataFrame()  # Return empty DataFrame if no data
    
    df = pd.DataFrame(rows, columns=["run_id", "uid", "hotkey", "task_name", "score", "success", "duration", "created_at", "evaluation_set_id", "sample_size"])
    return df
