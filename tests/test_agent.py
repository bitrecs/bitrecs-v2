import pytest
import uuid
import logging
from dotenv import load_dotenv
load_dotenv()
from queries.agent import create_agent, get_agent_by_id, get_agents_by_top_limit
from datetime import datetime, timezone
from models.agent import Agent, MessageExample, SamplingParams, AgentStatus

logger = logging.getLogger(__name__)


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
        miner_hotkey="sample_hotkey",
        name="Sample Agent",
        version_num=1,
        status=AgentStatus.screening_1,
        ip_address="127.0.0.1",  # Add ip_address to avoid NOT NULL violation
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
