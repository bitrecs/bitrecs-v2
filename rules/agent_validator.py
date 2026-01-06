from typing import Tuple
from models.agent import Agent
from utils.token import get_token_count


MAX_PROMPT_TOKENS = 50_000
MAX_SYSTEM_PROMPT_TOKENS = 10_000


def validate_artifact(agent: Agent) -> Tuple[bool, str]:    
    if agent.agent_id is not None:
        return False, "agent_id must not be set by the client"
    
    if len(agent.miner_hotkey) == 0:
        return False, "miner_hotkey must not be empty"
    if len(agent.name) == 0:
        return False, "name must not be empty"
    if agent.version_num <= 0:
        return False, "version_num must be greater than 0"
    if agent.miner_uid <= 0:
        return False, "miner_uid must be greater than 0"
    if len(agent.provider) == 0:
        return False, "provider must not be empty"
    if len(agent.model) == 0:
        return False, "model must not be empty"
    if len(agent.system_prompt_template) == 0:
        return False, "system_prompt_template must not be empty"
    if len(agent.user_prompt_template) == 0:
        return False, "user_prompt_template must not be empty"    
    if get_token_count(agent.system_prompt_template) > MAX_SYSTEM_PROMPT_TOKENS:
        return False, "system_prompt_template exceeds maximum token count"
    if get_token_count(agent.user_prompt_template) > MAX_PROMPT_TOKENS:
        return False, "user_prompt_template must not exceed maximum token count"
    
    if agent.status != 'screening_1':
        return False, "status must be 'screening_1' upon submission"
    
    return True, ""

