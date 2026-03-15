import json
from uuid import UUID
from typing import Optional, List, Dict, Any
from datetime import datetime
from utils.database import db_operation, DatabaseConnection

@db_operation
async def insert_inference(
    conn: DatabaseConnection,
    evaluation_run_id: UUID,
    provider: str,
    model: str,
    temperature: float,
    messages: List[Dict[str, Any]],
    status_code: Optional[int] = None,
    response: Optional[str] = None,
    num_input_tokens: Optional[int] = None,
    num_output_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    response_sent_at: Optional[datetime] = None
) -> UUID:
    """
    Insert a new inference record and return the generated inference_id.
    """
    result = await conn.fetchrow(
        """
        INSERT INTO inferences (
            evaluation_run_id, provider, model, temperature, messages,
            status_code, response, num_input_tokens, num_output_tokens,
            cost_usd, response_sent_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING inference_id
        """,
        evaluation_run_id, provider, model, temperature, json.dumps(messages),
        status_code, response, num_input_tokens, num_output_tokens,
        cost_usd, response_sent_at
    )
    return result['inference_id']