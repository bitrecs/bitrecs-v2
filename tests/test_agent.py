import os
import pytest
import uuid
import logging
from dotenv import load_dotenv
load_dotenv()
from rules.agent_validator import validate_artifact_template
from tests.test_template import MINER_YAML_PATH
from queries.agent import create_agent, get_agent_by_id, get_agents_by_top_limit
from datetime import datetime, timezone
from models.agent import Agent, MessageExample, SamplingParams, AgentStatus

logger = logging.getLogger(__name__)


def load_agent_from_yaml(miner_yaml_path):
    if not os.path.exists(miner_yaml_path):
        print(f"YAML file not found at path: {miner_yaml_path}")
        return
    with open(miner_yaml_path, 'r') as f:
        yaml_content = f.read()

    artifact = Agent.from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact)
    if not validated:
        raise ValueError(f"Artifact validation failed: {reason}")    
    return artifact   


@pytest.mark.asyncio
async def test_get_top_agents(db_setup):
    limit = 2
    agents = await get_agents_by_top_limit(limit)
    logger.info(f"Retrieved {len(agents)} top agents")
    assert isinstance(agents, list)
    assert len(agents) == limit


@pytest.mark.asyncio
async def test_insert_and_select_agent(db_setup):
    """Test inserting and selecting an Agent."""
    
    agent = Agent(
        agent_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        miner_hotkey="test_unit_sample_hotkey",
        name="Sample Agent Unit Test",
        version_num=1,
        status=AgentStatus.screening_1,
        ip_address="127.0.0.1", 
        miner_uid=123, 
        provider="sample_provider",
        model="sample_model",
        system_prompt_template="System prompt",
        user_prompt_template="User prompt",
        sampling_params=SamplingParams(temperature=0.7),
        fewshot_examples=[MessageExample(role="user", content="Hello")],
        eval_scores={"accuracy": 0.95}
    )

    agent_id = await create_agent(agent)
    db_agent = await get_agent_by_id(agent_id)

    assert db_agent is not None
    assert db_agent.agent_id == agent.agent_id


@pytest.mark.asyncio
async def test_load_agent_template_and_validate(db_setup):
    """Test loading an agent from YAML, validating, creating in DB, and round-trip serialization."""
    artifact = load_agent_from_yaml(MINER_YAML_PATH)
    assert artifact is not None
    assert isinstance(artifact, Agent)

    artifact.agent_id = uuid.uuid4()
    agent_id = await create_agent(artifact)
    db_agent = await get_agent_by_id(agent_id)

    assert db_agent is not None
    assert db_agent.agent_id == artifact.agent_id

    # Serialize to YAML
    agent_yaml = Agent.to_yaml(db_agent)
    assert isinstance(agent_yaml, str)

    # Deserialize back to Agent
    deserialized_agent = Agent.from_yaml(agent_yaml)
    assert isinstance(deserialized_agent, Agent)
    
    assert deserialized_agent.agent_id == db_agent.agent_id
    assert deserialized_agent.miner_hotkey == db_agent.miner_hotkey
    assert deserialized_agent.name == db_agent.name
    assert deserialized_agent.status == db_agent.status    
    assert deserialized_agent.miner_uid == db_agent.miner_uid
    assert deserialized_agent.provider == db_agent.provider
    assert deserialized_agent.model == db_agent.model
    assert deserialized_agent.system_prompt_template == db_agent.system_prompt_template
    assert deserialized_agent.user_prompt_template == db_agent.user_prompt_template
    assert deserialized_agent.sampling_params == db_agent.sampling_params
    assert deserialized_agent.eval_scores == db_agent.eval_scores



