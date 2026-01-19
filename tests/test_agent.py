import os
import pytest
import uuid
import logging
import numpy as np
from dotenv import load_dotenv
from llm.chutes import Chutes
from llm.open_router import OpenRouter
from rules.agent_comparer import AgentComparer
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





@pytest.fixture
def sample_agent1():
    return Agent(
        agent_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        miner_hotkey="hotkey1",
        name="Agent1",
        version_num=1,
        status=AgentStatus.screening_1,
        ip_address="127.0.0.1",
        miner_uid=1,
        provider="openai",
        model="gpt-3.5-turbo",
        system_prompt_template="You are a helpful assistant.",
        user_prompt_template="Answer the question: {{question}}",
        sampling_params=SamplingParams(temperature=0.7, top_p=0.9, max_tokens=100),
        fewshot_examples=[
            MessageExample(role="user", content="Hello"),
            MessageExample(role="assistant", content="Hi there")
        ],
        eval_scores={}
    )

@pytest.fixture
def sample_agent2():
    return Agent(
        agent_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        miner_hotkey="hotkey2",
        name="Agent2",
        version_num=1,
        status=AgentStatus.screening_1,
        ip_address="127.0.0.1",
        miner_uid=2,
        provider="openai",
        model="gpt-3.5-turbo",
        system_prompt_template="You are a helpful assistant.",
        user_prompt_template="Answer the question: {{question}}",
        sampling_params=SamplingParams(temperature=0.7, top_p=0.9, max_tokens=100),
        fewshot_examples=[
            MessageExample(role="user", content="Hello"),
            MessageExample(role="assistant", content="Hi there")
        ],
        eval_scores={}
    )


@pytest.fixture
def sample_agent3():
    return Agent(
        agent_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        miner_hotkey="hotkey3",
        name="Agent3",
        version_num=1,
        status=AgentStatus.screening_1,
        ip_address="192.0.0.1",
        miner_uid=42,
        provider="openai",
        model="mistral-nemo",
        system_prompt_template="You are a helpful assistant.",
        user_prompt_template="Answer the question: {{question}} to the best of your ability",
        sampling_params=SamplingParams(temperature=0.1, top_p=0.9, max_tokens=2048),
        fewshot_examples=[
            MessageExample(role="user", content="Hello sir"),
            MessageExample(role="assistant", content="Hi would you like to redeem?")
        ],
        eval_scores={}
    )

@pytest.mark.asyncio
async def test_open_router_embedding():
    """Test OpenRouter embedding generation."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    open_router = OpenRouter(key=api_key, model="qwen/qwen3-embedding-8b")
    embeddings = open_router.get_embeddings("Test embedding")
    
    assert isinstance(embeddings, list), "Embeddings should be a list"
    assert len(embeddings) > 0, "Embeddings should not be empty"
    assert all(isinstance(x, (float, int)) for x in embeddings), \
        f"All embedding values should be numeric, got types: {set(type(x).__name__ for x in embeddings[:10])}"        
    assert 4096 == len(embeddings), f"Unexpected embedding dimension: {len(embeddings)}"    
    logger.info(f"✓ Obtained embedding of length {len(embeddings)} from OpenRouter")

@pytest.mark.asyncio
async def test_chutes_embedding():
    """Test Chutes embedding generation."""  
    api_key = os.getenv("CHUTES_API_KEY", "")
    chutes = Chutes(key=api_key, model="qwen/qwen3-embedding-8b")
    embeddings = chutes.get_embeddings("Test embedding")

    assert isinstance(embeddings, list), "Embeddings should be a list"
    assert len(embeddings) > 0, "Embeddings should not be empty"
    assert all(isinstance(x, (float, int)) for x in embeddings), \
        f"All embedding values should be numeric, got types: {set(type(x).__name__ for x in embeddings[:10])}"        
    assert 4096 == len(embeddings), f"Unexpected embedding dimension: {len(embeddings)}"    
    logger.info(f"✓ Obtained embedding of length {len(embeddings)} from Chutes")



@pytest.mark.asyncio
async def test_agent_comparator_cosine_distance(sample_agent1, sample_agent2):
    """
    Simple unit test for AgentComparator.cosine_distance.
    Tests that distance is a float between 0 and 2, and identical agents have distance ~0.
    Assumes the embedding server is running at http://localhost:8080.
    """
    chutes = Chutes(key=os.getenv("CHUTES_API_KEY", ""), model="qwen/qwen3-embedding-8b")
    comparator = AgentComparer(provider=chutes)
    
    # Test distance between identical agents (should be ~0)
    distance_self = await comparator.cosine_distance(sample_agent1, sample_agent1)
    assert isinstance(distance_self, float)
    assert np.isclose(distance_self, 0.0, atol=1e-6), f"Self-distance should be ~0, got {distance_self}"
    
    # Test distance between similar agents (should be low)
    distance_similar = await comparator.cosine_distance(sample_agent1, sample_agent2)
    assert isinstance(distance_similar, float)
    assert 0 <= distance_similar <= 2, f"Distance should be between 0 and 2, got {distance_similar}"
    assert distance_similar < 0.1, f"Similar agents should have low distance, got {distance_similar}"  # Adjust threshold as needed


@pytest.mark.asyncio
async def test_agent_comparator_embedding_distance(sample_agent1, sample_agent3):    
    #provider = OpenRouter(key=os.getenv("OPENROUTER_API_KEY", ""), model="qwen/qwen3-embedding-8b")
    provider = Chutes(key=os.getenv("CHUTES_API_KEY", ""), model="qwen/qwen3-embedding-8b")
    comparer = AgentComparer(provider=provider)
    threshold = 0.08

    # diff agents
    distance = await comparer.cosine_distance(sample_agent1, sample_agent3)
    assert isinstance(distance, float)
    assert 0 <= distance <= 2, f"Distance should be between 0 and 2, got {distance}"
    assert distance > threshold, f"Different agents should have higher distance, got {distance}"  # Adjust threshold as needed
    


