import re
import utils.logger as logger
from typing import Tuple
from collections import Counter
from models.agent import Agent
from llm.llm_provider import LLM
from utils.token import get_token_count
from jinja2 import Template, TemplateSyntaxError, Environment, nodes

MAX_SYSTEM_PROMPT_TOKENS = 5_000
MAX_PROMPT_TOKENS = 10_000

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

VARIABLE_COUNT_RESTRICTIONS = {
    'product_catalog': 1,
    'order_json': 1,
    'cart_json': 1
}
    
def count_raw_template_variables(template_str: str) -> dict:
    result = {var: 0 for var in VARIABLE_COUNT_RESTRICTIONS.keys()}
    for var in VARIABLE_COUNT_RESTRICTIONS.keys():
        pattern = r'{{\s*' + re.escape(var) + r'\s*}}'
        matches = re.findall(pattern, template_str)
        result[var] = len(matches)
    return result


def validate_artifact_template(agent: Agent, raw_source: str = None) -> Tuple[bool, str]:
    print(f"Validating artifact template for agent: {agent.name}")
    logger.info(f"\033[34mValidating artifact template for agent: {agent.name}\033[0m")
    if len(agent.name) == 0 or len(agent.name) > 30:
        return False, "name must not be empty and must not exceed 30 characters"
    if not re.match(r'^[a-zA-Z0-9 ]{1,30}$', agent.name):
        return False, "name must be 1-30 alphanumeric characters only (letters and numbers, no special characters)"
    if agent.version_num != 1:
        return False, "version_num must be 1"
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
    ALLOWED_PROVIDERS = [LLM.CHUTES]
    if provider not in ALLOWED_PROVIDERS:
        return False, f"provider '{provider.name}' is currently not supported. Supported providers are: {', '.join([p.name for p in ALLOWED_PROVIDERS])}"
    
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
    matched_vars = Counter()
    invalid_vars = set()
    variable_counts = {var: 0 for var in VALID_TEMPLATE_VARIABLES}
    for template_str, template_name in [
        (agent.system_prompt_template, "system_prompt_template"),
        (agent.user_prompt_template, "user_prompt_template")
    ]:
        try:
            ast = env.parse(template_str)            
            for node in ast.find_all(nodes.Name):
                var = node.name
                print(f"Found variable '{var}' in {template_name}")
                matched_vars[var] += 1
                if var in VALID_TEMPLATE_VARIABLES:
                    variable_counts[var] += 1
               
        except Exception as e:
            return False, f"Error parsing variables in {template_name}: {e}"
        
    if len(matched_vars) == 0:
        return False, "No valid template variables found in either prompt template"

    result = ""
    test_passed = True    
    for var, max_count in VARIABLE_COUNT_RESTRICTIONS.items():
        print(f"Checking variable '{var}' with count {variable_counts[var]} against max count {max_count}")
        if variable_counts[var] > max_count:
            test_passed = False
            invalid_vars.add(var)
            result += f"Variable '{var}' appears {variable_counts[var]} times in TEMPLATE but may only appear {max_count} time(s)\n"

    if raw_source:        
        matches = count_raw_template_variables(raw_source)        
        for var, count in matches.items():
            if var in VARIABLE_COUNT_RESTRICTIONS:
                max_count = VARIABLE_COUNT_RESTRICTIONS[var]
                print(f"Checking raw variable '{var}' with count {count} against max count {max_count}")
                if count > max_count:
                    test_passed = False
                    invalid_vars.add(var)
                    result += f"Variable '{var}' appears {count} times in the RAW TEMPLATE but may only appear {max_count} time(s).\n"

    if not test_passed:
        result += f"\n Used variables: {dict(matched_vars)}"
        logger.info(f"\033[31mTemplate validation failed.\n{result}\033[0m")
        return False, result
    
    logger.info(f"\033[32mTemplate validation successful. Used variables: {dict(matched_vars)} \033[0m")
    return True, f"Valid template. Used variables: {dict(matched_vars)}"


