import os
from pathlib import Path
from models.agent import Agent
from rules.agent_validator import validate_artifact_template

ROOT_DIR = Path(__file__).parent.parent
MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "miner_artifact.yaml")
BROKEN_MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "invalid_artifact.yaml")

def test_template_contains_valid_vars():
    if not os.path.exists(MINER_YAML_PATH):
        print(f"YAML file not found at path: {MINER_YAML_PATH}")
        return
    with open(MINER_YAML_PATH, 'r') as f:
        yaml_content = f.read()

    artifact = Agent.from_yaml(yaml_content)    
    validated, reason = validate_artifact_template(artifact, yaml_content)
    assert validated, f"Artifact validation failed: {reason}"
    print(f"Valid, found variables: {reason}")
    


def test_template_contains_excess_vars():
    if not os.path.exists(BROKEN_MINER_YAML_PATH):
        print(f"YAML file not found at path: {BROKEN_MINER_YAML_PATH}")
        return
    with open(BROKEN_MINER_YAML_PATH, 'r') as f:
        yaml_content = f.read()

    artifact = Agent.from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact, yaml_content)
    assert not validated, f"Artifact validation should have failed but passed: {reason}"
    print(f"Invalid, found variables: {reason}")
    


def test_template_contains_excess_vars_2():
    BROKEN_MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "invalid_artifact_vars.yaml")
    if not os.path.exists(BROKEN_MINER_YAML_PATH):
        print(f"YAML file not found at path: {BROKEN_MINER_YAML_PATH}")
        return
    with open(BROKEN_MINER_YAML_PATH, 'r') as f:
        yaml_content = f.read()

    artifact = Agent.from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact, yaml_content)
    print(f"\033[33mValidation result: {validated}, reason: {reason}\033[0m")

    assert not validated, f"Artifact validation should have failed: {reason}"
    