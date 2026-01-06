from typing import Optional
from uuid import UUID
import json
from models.agent import AgentStatus
from models.artifact import Artifact
from utils.database import DatabaseConnection, db_operation


@db_operation
async def get_artifact_by_id(conn: DatabaseConnection, artifact_id: UUID) -> Optional[Artifact]:
    result = await conn.fetchrow(
        """
        SELECT *
        FROM artifacts 
        WHERE artifact_id = $1
        LIMIT 1
        """,
        artifact_id
    )

    if result is None:
        return None

    # Parse JSON strings back to Python objects for Pydantic validation
    result = dict(result)
    result['sampling_params'] = json.loads(result['sampling_params']) if result['sampling_params'] else {}
    result['fewshot_examples'] = json.loads(result['fewshot_examples']) if result['fewshot_examples'] else []
    result['eval_scores'] = json.loads(result['eval_scores']) if result['eval_scores'] else {}

    return Artifact(**result)


@db_operation
async def create_artifact(conn: DatabaseConnection, artifact: Artifact) -> UUID:
    # Removed agent_text and S3 upload as they don't apply to artifacts schema

    result = await conn.fetchval(
        """
        INSERT INTO artifacts (
            artifact_id, parent_id, created_at, miner_hotkey, miner_uid, provider, model,
            system_prompt_template, user_prompt_template, sampling_params, fewshot_examples, eval_scores
        )
        VALUES ($1, $2, NOW()::text, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        RETURNING artifact_id
        """,
        artifact.artifact_id,
        artifact.parent_id,
        artifact.miner_hotkey,
        artifact.miner_uid,
        artifact.provider,
        artifact.model,
        artifact.system_prompt_template,
        artifact.user_prompt_template,
        json.dumps(artifact.sampling_params.model_dump()),  # Serialize to JSON string for jsonb
        json.dumps([ex.model_dump() for ex in artifact.fewshot_examples]) if artifact.fewshot_examples else None,  # Serialize list to JSON string
        json.dumps(artifact.eval_scores or {})  # Serialize dict to JSON string
    )
    return result
