import os
import pytest
import uuid
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timezone
from utils.database import initialize_database, deinitialize_database
from models.artifact import Artifact, MessageExample, SamplingParams
from queries.artifact import create_artifact, get_artifact_by_id

@pytest.fixture(scope="function", autouse=True)
async def db_setup():
    """Initialize database once per test session and clean up after."""   
    await initialize_database(
        username=os.getenv("DATABASE_USERNAME"),
        password=os.getenv("DATABASE_PASSWORD"),
        host=os.getenv("DATABASE_HOST"),
        port=int(os.getenv("DATABASE_PORT", 5432)),
        name=os.getenv("DATABASE_NAME")
    )
    yield
    await deinitialize_database()


async def test_insert_and_select_artifact(db_setup):  # Add fixture param if needed, but autouse handles it
    """Test inserting and selecting an Artifact."""
        
    # Create a sample Artifact
    artifact = Artifact(
        artifact_id=uuid.uuid4(),
        parent_id=None,
        created_at=datetime.now(timezone.utc).isoformat(),
        miner_hotkey="sample_hotkey",
        miner_uid=123, 
        provider="sample_provider",
        model="sample_model",
        system_prompt_template="System prompt",
        user_prompt_template="User prompt",
        sampling_params=SamplingParams(temperature=0.7),
        fewshot_examples=[MessageExample(role="user", content="Hello")],
        eval_scores={"accuracy": 0.95}
    )    

    artifact_id = await create_artifact(artifact)
    db_artifact = await get_artifact_by_id(artifact_id)

    assert db_artifact is not None
    assert db_artifact.artifact_id == artifact.artifact_id

    # Add assertions or select logic here
    # e.g., fetched = await get_artifact(artifact.artifact_id)
    # assert fetched.miner_hotkey == artifact.miner_hotkey

