import logging
from typing import Tuple
from models.agent import Agent
from utils.token import get_token_count
from jinja2 import Template, TemplateSyntaxError, Environment, nodes

logger = logging.getLogger(__name__)

MAX_PROMPT_TOKENS = 50_000
MAX_SYSTEM_PROMPT_TOKENS = 10_000

VALID_TEMPLATE_VARIABLES = {
    'current_date',
    'sku',
    'num_recs',
    'persona',
    'product_catalog',        
    'sku_info',
    'cart_json',
    'order_json'
}

def validate_artifact_template(agent: Agent) -> Tuple[bool, str]:    
    # if agent.agent_id is not None:
    #     return False, "agent_id must not be set by the client" 
    
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
    
    try:
        Template(agent.system_prompt_template)
    except TemplateSyntaxError as e:
        return False, f"system_prompt_template is not a valid Jinja2 template: {e}"
    try:
        Template(agent.user_prompt_template)
    except TemplateSyntaxError as e:
        return False, f"user_prompt_template is not a valid Jinja2 template: {e}"
    
    env = Environment()
    matched_vars = set()    
    for template_str, template_name in [(agent.system_prompt_template, "system_prompt_template"), (agent.user_prompt_template, "user_prompt_template")]:
        try:
            ast = env.parse(template_str)
            variables_used = set()
            for node in ast.find_all(nodes.Name):
                variables_used.add(node.name)            
            
            invalid_vars = variables_used - VALID_TEMPLATE_VARIABLES
            if invalid_vars:
                return False, f"{template_name} contains invalid variable(s): {', '.join(invalid_vars)}. Allowed variables are: {', '.join(sorted(VALID_TEMPLATE_VARIABLES))}"
            
            matched_vars.update(variables_used)
        except Exception as e:
            return False, f"Error parsing variables in {template_name}: {e}"

    if len(matched_vars) == 0:
        return False, "No valid template variables found in either prompt template"
    
    #logger.info(f"\033[32mTemplate validation successful. Used variables: {', '.join(sorted(matched_vars))} \033[0m")
    return True, f"Valid template. Used variables: {', '.join(sorted(matched_vars))}"
    

