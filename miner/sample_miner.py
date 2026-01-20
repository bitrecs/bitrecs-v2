import os
import sys
import time
import httpx
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pathlib import Path
from models.agent import Agent
from rules.agent_validator import validate_artifact_template
import validator.config as config
import utils.logger as logger


ROOT_DIR = Path(__file__).parent.parent
MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "miner_input.yaml")

#SERVICE_URL = "http://localhost:8000"
SERVICE_URL =  config.RIDGES_PLATFORM_URL


def upload_prompt():
    #LOAD AND VALIDATE TEMPLATE
    if not os.path.exists(MINER_YAML_PATH):
        print(f"YAML file not found at path: {MINER_YAML_PATH}")
        return
    with open(MINER_YAML_PATH, 'r') as f:
        yaml_content = f.read()

    artifact = Agent.from_yaml(yaml_content)
    validated, reason = validate_artifact_template(artifact)
    if not validated:
        print(f"Artifact validation failed: {reason}")
        return   
    
    print(f"Valid, found variables: {reason}")
    
    #UPLOAD TEMPLATE
    headers = {
        "Content-Type": "application/json",
        "x-api-key": "your_api_key_here",
        "x-signature": "your_signature_here",
        "x-timestamp": "your_timestamp_here",
        "x-nonce": "your_nonce_here"
    }      
    artifact.name = f"{artifact.name} - Test {int(time.time())}"
    with httpx.Client(base_url=SERVICE_URL, headers=headers) as client:
        response = client.post(
            "/artifact",
            json=artifact.model_dump(mode="json")
        )
        response.raise_for_status()
        if response.status_code != 201:
            print(f"Failed to upload artifact: {response.status_code} - {response.text}")
            return
        
        print(f"Upload response status: {response.status_code}")
        print(f"Upload response data: {response.json()}")

    #fetch artifact
    artifact_id = response.json().get("artifact_id")
    if artifact_id:
        with httpx.Client(base_url=SERVICE_URL, headers=headers) as client:
            fetch_response = client.get(f"/artifact/{artifact_id}")
            fetch_response.raise_for_status()
            #print(f"Fetched artifact data: {fetch_response.json()}")
            agent_json = fetch_response.json()
            agent = Agent(**agent_json)
            print(f"Reconstructed Artifact ID: {agent.agent_id}")
            logger.info(f"\033[32mSuccess submitted new Artifact: {agent.name} \033[0m")
            logger.info(f"\033[32mArtifact ID: {agent.agent_id} \033[0m")
            logger.info(f"\033[32mArtifact Provider: {agent.provider} \033[0m")
            logger.info(f"\033[32mArtifact Model: {agent.model} \033[0m")


if __name__ == "__main__":
    upload_prompt()