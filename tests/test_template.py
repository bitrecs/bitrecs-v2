import os
from pathlib import Path
from models.agent import Agent
from rules.agent_validator import validate_artifact_template

ROOT_DIR = Path(__file__).parent.parent
MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "miner_input.yaml")


def test_template_contains_valid_vars():
    if not os.path.exists(MINER_YAML_PATH):
        print(f"YAML file not found at path: {MINER_YAML_PATH}")
        return
    with open(MINER_YAML_PATH, 'r') as f:
        yaml_content = f.read()

    artifact = Agent.load_from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact)
    assert validated, f"Artifact validation failed: {reason}"
    print(f"Valid, found variables: {reason}")
    

