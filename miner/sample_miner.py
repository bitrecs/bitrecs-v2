import os
import sys
import httpx
import pickle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
load_dotenv()
from typing import Tuple
from pathlib import Path
from utils.models import normalize_model_name
from models.agent import Agent
from rules.agent_validator import validate_artifact_template
from utils.gist import get_gist, get_gist_created_at
import utils.logger as logger
from bittensor import Subtensor
from version import __version__ as this_version
from bittensor_wallet.wallet import Wallet
from bittensor.extras import timelock
from utils.verify import verify_submission_signature


ROOT_DIR = Path(__file__).parent.parent
MINER_YAML_PATH = os.path.join(ROOT_DIR, "miner", "miner_artifact.yaml")

#SERVICE_URL = "http://localhost:8000"
SERVICE_URL =  os.getenv("RIDGES_PLATFORM_URL", "")
if not SERVICE_URL:
    raise ValueError("RIDGES_PLATFORM_URL environment variable is not set. Please set it to the API endpoint URL.")

CHAIN_ENDPOINT = os.getenv("SUBTENSOR_ADDRESS")
NETWORK = os.getenv("SUBTENSOR_NETWORK", "test")
SUBTENSOR = Subtensor(network=CHAIN_ENDPOINT or NETWORK)
NETUID = int(os.getenv("NETUID", 296))

WALLET_NAME = os.getenv("MINER_WALLET_NAME")
WALLET_HOTKEY = os.getenv("MINER_HOTKEY_NAME")
MINER_WALLET_HOTKEY = os.getenv("MINER_WALLET_HOTKEY")
MINER_WALLET = Wallet(WALLET_NAME, WALLET_HOTKEY)

GITHUB_ACCOUNT = "janusdotai"
GIST_ID = "dfbcc6e1abdaaa365ab4ce6b7e6d785c"


"""
Miner Submission Process

1) Aquire fresh hotkey (single use only)
2) Create artifact.yaml, test/tune locally using eval-suite
3) When ready, create a private github GIST with said artifact (ensure yaml file format)
4) Run this script which will do the following:

a: download and verify the artifact from the GIST
b: timelock encrypt submission details (github account, gist id, hotkey, timestamp) with a short duration (e.g. 5 blocks)
c: submit packge to API with commitment proof and signature
d: fetch package back from API to confirm successful submission

"""

def timelock_encrypt(data: str, block_duration: int) -> Tuple[bytes, int]:
    """Encrypt data using timelock encryption."""
    encrypted_data, block = timelock.encrypt(data.encode('utf-8'), block_duration)
    return encrypted_data, block

def timelock_decrypt(encrypted_data: bytes) -> str:
    """Decrypt data using timelock decryption."""
    decrypted_data = timelock.wait_reveal_and_decrypt(encrypted_data, return_str=True)
    return decrypted_data  


def upload_prompt():
    raise NotImplementedError("This function is a work in progress and is not yet implemented.")
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


def submit_prompt_from_gist():
    gist_created_at = get_gist_created_at(GIST_ID)
    gist_raw_data = get_gist(GITHUB_ACCOUNT, GIST_ID)   
    artifact = Agent.from_yaml(gist_raw_data)
    validated, reason = validate_artifact_template(artifact)
    assert validated, f"Artifact validation failed: {reason}"
    
    # Step 2: Create MinerSubmission instance with signature
    preamble = f"{gist_created_at.isoformat()}:{GITHUB_ACCOUNT}:{GIST_ID}:{MINER_WALLET_HOTKEY}"
    print(f"Data to be signed: {preamble}")
    signature = MINER_WALLET.hotkey.sign(preamble).hex()
    print(f"Generated signature: {signature}")
    
    from models.miner_submission import MinerSubmission
    submission = MinerSubmission(
        created_at=gist_created_at.isoformat(),
        github_account=GITHUB_ACCOUNT,
        gist_id=GIST_ID,
        hotkey=MINER_WALLET_HOTKEY,      
        signature=signature
    )
    print(submission)
    assert submission.created_at == gist_created_at.isoformat()
    assert submission.github_account == GITHUB_ACCOUNT
    assert submission.gist_id == GIST_ID
    assert submission.hotkey == MINER_WALLET_HOTKEY
    assert submission.signature == signature

    v = verify_submission_signature(submission)
    print(f"Signature verification result: {v}")
    assert v, "Signature verification should succeed"

    byte_data = pickle.dumps(submission)
    n_blocks = 1
    encrypted, reveal_round = timelock.encrypt(byte_data, n_blocks)
    print(f"Encrypted submission (hex): {encrypted.hex()}")
    decrypted_bytes = timelock.wait_reveal_and_decrypt(encrypted)
    decrypted_submission = pickle.loads(decrypted_bytes)
    print(f"Decrypted submission: {decrypted_submission}")
    assert decrypted_submission == submission, "Decrypted submission should match the original submission"



if __name__ == "__main__":
    logger.info(f"Starting sample miner with version: {this_version}")
    logger.info(f"wallet: {WALLET_NAME}, hotkey: {WALLET_HOTKEY}")

    # print("Retrieving existing commitments for miner wallet...")
    # get_commitments(MINER_WALLET.hotkey.ss58_address)        
    # exit()

    print("Beginning artifact upload process...")
    upload_prompt()