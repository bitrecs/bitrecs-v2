from typing import Tuple
from models.agent import Agent
from utils.token import get_token_count
from jinja2 import Template, TemplateSyntaxError


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


def validate_artifact_template(agent: Agent) -> Tuple[bool, str]:
    """Validates an Agent artifact update request."""    
    
    if len(agent.system_prompt_template) == 0:
        return False, "system_prompt_template must not be empty"
    if len(agent.user_prompt_template) == 0:
        return False, "user_prompt_template must not be empty"    
    
    if get_token_count(agent.system_prompt_template) > MAX_SYSTEM_PROMPT_TOKENS:
        return False, "system_prompt_template exceeds maximum token count"
    if get_token_count(agent.user_prompt_template) > MAX_PROMPT_TOKENS:
        return False, "user_prompt_template exceeds maximum token count"    

    try:
        Template(agent.system_prompt_template)
    except TemplateSyntaxError as e:
        return False, f"system_prompt_template is not a valid Jinja2 template: {e}"
    try:
        Template(agent.user_prompt_template)
    except TemplateSyntaxError as e:
        return False, f"user_prompt_template is not a valid Jinja2 template: {e}"
    
    # check for valid variables used if typical jinja templates are present. 
    # We allow variables: 'current_date',  '{{sku}}', '{{persona}}', '{{product_catalog}}', '{{num_recs}}', '{{sku_info}}', '{{cart_json}}', '{{order_json}}'
    valid_test_vars = {
        'skus',
        'persona',
        'product_catalog',
        'num_recs',
        'sku_info',
        'cart_json',
        'order_json'
    }
    for template_str, template_name in [(agent.system_prompt_template, "system_prompt_template"), (agent.user_prompt_template, "user_prompt_template")]:
        template = Template(template_str)
        for var in template.make_module().__dict__.keys():
            if var not in valid_test_vars and not var.startswith('_'):
                return False, f"{template_name} contains invalid variable '{var}'. Allowed variables are: {', '.join(valid_test_vars)}"

    
    return True, ""


def check_key_in_prompt(key, prompt) -> bool:
    """Check if a key is present in a prompt template."""
    template = Template(prompt)
    return key in template.make_module().__dict__


