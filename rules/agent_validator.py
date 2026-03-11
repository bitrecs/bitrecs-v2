import utils.logger as logger
from typing import Tuple
from models.agent import Agent
from llm.llm_provider import LLM
from utils.token import get_token_count
from jinja2 import Template, TemplateSyntaxError, Environment, nodes

MAX_PROMPT_TOKENS = 10_000
MAX_SYSTEM_PROMPT_TOKENS = 5_000

VALID_TEMPLATE_VARIABLES = {
    'current_date',
    'product_catalog',
    'sku',
    'sku_info',
    'num_recs',    
    'persona',
    'cart_json',
    'order_json'
}

# Variables that must only appear once in the template
VARIABLE_COUNT_RESTRICTIONS = {
    'product_catalog': 1,
    'order_json': 1,
    'cart_json': 1    
}

def validate_artifact_template(agent: Agent) -> Tuple[bool, str]:
    if len(agent.name) == 0:
        return False, "name must not be empty"
    if agent.version_num <= 0:
        return False, "version_num must be greater than 0" 
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
    
    if LLM.is_valid(agent.provider) == False:
        return False, f"provider '{agent.provider}' is not a supported LLM provider"
    
    provider = LLM.try_parse(agent.provider)
    ALLOWED_PROVIDERS = [LLM.CHUTES, LLM.OPEN_ROUTER]
    if provider not in ALLOWED_PROVIDERS:
        return False, f"provider '{agent.provider}' is currently not supported. Supported providers are: {', '.join(ALLOWED_PROVIDERS)}"
    
    if ":free" in agent.model.lower():
        return False, "Free models are not supported"
    
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
    variable_counts = {var: 0 for var in VARIABLE_COUNT_RESTRICTIONS}
    for template_str, template_name in [
        (agent.system_prompt_template, "system_prompt_template"),
        (agent.user_prompt_template, "user_prompt_template")
    ]:
        try:
            ast = env.parse(template_str)
            variables_used = set()
            for node in ast.find_all(nodes.Name):
                variables_used.add(node.name)
                if node.name in VARIABLE_COUNT_RESTRICTIONS:
                    variable_counts[node.name] += 1

            invalid_vars = variables_used - VALID_TEMPLATE_VARIABLES
            if invalid_vars:
                return False, (
                    f"{template_name} contains invalid variable(s): {', '.join(invalid_vars)}. "
                    f"Allowed variables are: {', '.join(sorted(VALID_TEMPLATE_VARIABLES))}"
                )

            matched_vars.update(variables_used)
        except Exception as e:
            return False, f"Error parsing variables in {template_name}: {e}"

    # Check variable count restrictions
    for var, max_count in VARIABLE_COUNT_RESTRICTIONS.items():
        if variable_counts[var] > max_count:
            return False, (
                f"Variable '{var}' appears {variable_counts[var]} times, "
                f"but may only appear {max_count} time(s) in the templates."
            )

    if len(matched_vars) == 0:
        return False, "No valid template variables found in either prompt template"
    
    logger.info(f"\033[32mTemplate validation successful. Used variables: {', '.join(sorted(matched_vars))} \033[0m")
    return True, f"Valid template. Used variables: {', '.join(sorted(matched_vars))}"


