import os
import sys
import time
import httpx
import hashlib
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
load_dotenv()
import utils.logger as logger
from pathlib import Path
from datetime import datetime, timezone
from utils.models import normalize_model_name
from models.agent import Agent
from rules.agent_validator import validate_artifact_template
from rules.agent_comparer import AgentComparer
from bittensor import Subtensor
from version import __version__ as this_version
from bittensor_wallet.wallet import Wallet
from bittensor.extras import timelock

ROOT_DIR = Path(__file__).parent.parent
MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "miner_artifact.yaml")

#SERVICE_URL = "http://localhost:8000"
SERVICE_URL =  os.getenv('RIDGES_PLATFORM_URL', '')
if not SERVICE_URL:
    raise ValueError("RIDGES_PLATFORM_URL environment variable is not set. Please set it to the API endpoint URL.")

CHAIN_ENDPOINT = os.getenv('SUBTENSOR_ADDRESS')
NETWORK = os.getenv('SUBTENSOR_NETWORK', 'test')
SUBTENSOR = Subtensor(network=CHAIN_ENDPOINT or NETWORK)
NETUID = int(os.getenv('NETUID', 296))

WALLET_NAME = os.getenv('MINER_WALLET_NAME')
WALLET_HOTKEY = os.getenv('MINER_HOTKEY_NAME')

MINER_WALLET = Wallet(WALLET_NAME, WALLET_HOTKEY)


TEST_GIST = "https://gist.github.com/janusdotai/dfbcc6e1abdaaa365ab4ce6b7e6d785c"


"""
Miner Submission Process

1) Aquire fresh hotkey (single use only)
2) Create artifact.yaml, test/tune locally using eval-suite
3) When ready, create a private github GIST with said artifact (ensure yaml file format)
4) Run this script which will do the following:

a: download and verify the artifact from the GIST
b: timelock encrypt hotkey + artifact
c: submit packge to API with commitment proof and signature
d: fetch package back from API to confirm successful submission

"""

def timelock_encrypt(data: str, block_duration: int) -> str:
    """Encrypt data using timelock encryption."""
    encrypted_data = timelock.encrypt(data.encode('utf-8'), block_duration)
    return encrypted_data.hex()


def get_commitments(hotkey: str):
    commitments = SUBTENSOR.get_all_commitments(netuid=NETUID)
    
    print(f"Total commitments retrieved: {len(commitments)}")
    print(commitments)
    for key, value in commitments.items():
        print(key)
        print(value)

    return


   

def hash_and_commit(artifact: Agent) -> bool:
    result = False
    hash_fields = AgentComparer.get_agent_hash_fields(artifact)
    print(f"Hash fields for artifact: {hash_fields}")        
    sha256_hash = f"0x{AgentComparer.get_agent_hash(artifact)}"
    print(f"Generated SHA256 hash for artifact: {sha256_hash}")
    epoch_ns = int(datetime.now(tz=timezone.utc).timestamp() * 1_000_000_000)    
    data = f"{sha256_hash}:{epoch_ns}"
    print(f"Data to be committed: {data}")
    signature = MINER_WALLET.sign(data.encode('utf-8'))
    print(f"Generated signature for commitment: {signature}")

    #return False

    print("starting commitment submission...")
    ext = SUBTENSOR.set_commitment(
        wallet=MINER_WALLET,
        netuid=NETUID,
        data=data        
    )
    print(f"Commitment extrinsic: {ext}")   
    if ext and ext.success:
        print(f"Artifact commitment successful with hash: {sha256_hash}")
        ext_hash = ext.extrinsic_receipt.get('hash')
        result = True
    else:
        print(f"Artifact commitment failed for hash: {sha256_hash}")
    return result


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
    
    if 1==1:
        commited = hash_and_commit(artifact)
        print(f"Artifact commit status: {commited}")
        if not commited:
            print("Artifact commitment failed, aborting upload.")
            return
    
    print(f"Valid, found variables: {reason}")  
    
    #UPLOAD TEMPLATE
    headers = {
        "Content-Type": "application/json",
        "x-api-key": "your_api_key_here",
        "x-signature": "your_signature_here",
        "x-timestamp": "your_timestamp_here",
        "x-nonce": "your_nonce_here",
        "x-commitment": "your_commitment_here"

    }         

    model_name = normalize_model_name(artifact.model, should_lower=True)
    print(f"Normalized model name for upload: \033[32m{model_name}\033[0m")
    artifact.name = f"Test {artifact.name} - {model_name}"
    with httpx.Client(base_url=SERVICE_URL, headers=headers) as client:
        response = client.post(
            "/artifact",
            json=artifact.model_dump(mode="json"),
            timeout=180
        )
        
        if response.status_code == 201:
            print(f"Upload response status: {response.status_code}")
            print(f"Upload response data: {response.json()}")
        else:
            # Print full error details for non-201, including 409
            print(f"Failed to upload artifact: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error details: {error_data}")
                if response.status_code == 409:
                    print("Similarity rejection details:")
                    for agent in error_data.get("similar_agents", []):
                        print(f"  - Agent ID: {agent['agent_id']}, Distance: {agent['distance']}, Similarity: {agent['similarity_score']}")
            except Exception:
                print(f"Response text: {response.text}")
            return  # Or handle as needed
    
    logger.info("Artifact uploaded successfully, proceeding to fetch.")
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
    logger.info(f"Starting sample miner with version: {this_version}")
    logger.info(f"wallet: {WALLET_NAME}, hotkey: {WALLET_HOTKEY}")

    print("Retrieving existing commitments for miner wallet...")
    get_commitments(MINER_WALLET.hotkey.ss58_address)        
    exit()

    print("Beginning artifact upload process...")
    upload_prompt()