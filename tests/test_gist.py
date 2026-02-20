import os
import pytest
import httpx
from dotenv import load_dotenv

from utils.subtensor import get_subtensor
load_dotenv()
from models.agent import Agent
from bittensor_wallet import Wallet
from datetime import datetime, timezone
from rules.agent_validator import validate_artifact_template
from utils.commitment import commit_to_chain, commit_to_chain_with_wallet, get_miner_commitments, is_commitment_valid
from utils.gist import get_gist, get_gist_created_at, get_gist_sha_commits
from models.miner_submission import MinerSubmission


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

GITHUB_ACCOUNT = "janusdotai"
GIST_ID = "944bf7d082c37ef782fd5be9342a7da8"

MINER_WALLET_NAME = os.getenv("MINER_WALLET_NAME")
MINER_WALLET_HOTKEY_NAME = os.getenv("MINER_WALLET_HOTKEY_NAME")
MINER_WALLET_HOTKEY = os.getenv("MINER_WALLET_HOTKEY")
MINER_WALLET = Wallet(MINER_WALLET_NAME, MINER_WALLET_HOTKEY_NAME)


def test_download_gist():
    raw_url = f"https://gist.githubusercontent.com/{GITHUB_ACCOUNT}/{GIST_ID}/raw"
    with httpx.Client(follow_redirects=True) as client:
        response = client.get(raw_url, timeout=15.0)
        if response.status_code == 200:
            content = response.text
            save_path = os.path.join(CURRENT_DIR, "artifact.yaml")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            print("Downloaded artifact.yaml successfully")
            artifact = Agent.from_path(save_path)
            validated, reason = validate_artifact_template(artifact)
            assert validated, f"Artifact validation failed: {reason}"
        else:
            print(f"Failed: {response.status_code} - {response.reason_phrase}")

    if os.path.exists(save_path):
        os.remove(save_path)


def test_gist_created_at():
    created_at = get_gist_created_at(GIST_ID)
    print(f"Gist created at: {created_at.isoformat()}")
    assert isinstance(created_at, datetime), "created_at should be a datetime object"
    second_diff = (datetime.now(timezone.utc) - created_at).total_seconds()
    print(f"Gist age in seconds: {second_diff}")
    assert second_diff > 0, "Gist should be created in the past"
    minute_diff = second_diff / 60
    print(f"Gist age in minutes: {minute_diff}")
    hour_diff = minute_diff / 60
    print(f"Gist age in hours: {hour_diff}")


@pytest.mark.asyncio
async def test_create_commitment():    
    gist_raw_data = get_gist(GITHUB_ACCOUNT, GIST_ID)
    artifact = Agent.from_yaml(gist_raw_data)
    validated, reason = validate_artifact_template(artifact)
    assert validated, f"Artifact validation failed: {reason}"   
    
    commitment_result = await commit_to_chain(GITHUB_ACCOUNT, GIST_ID, MINER_WALLET_NAME, MINER_WALLET_HOTKEY_NAME)
    print(f"Commitment result: {commitment_result}")
    assert commitment_result, "Commitment to chain should succeed"


@pytest.mark.asyncio
async def test_get_miner_commitments():
    miner_commitments = await get_miner_commitments(MINER_WALLET_HOTKEY)
    print(f"Miner commitments: {miner_commitments}")
    success = 0
    errors = 0
    if not miner_commitments:
        print("No commitments found for the miner wallet.")
    else:
        for i, (block, json_str) in enumerate(miner_commitments):
            try:
                print(f"Commitment {i}: ({block}, {json_str})")
                commitment_data = json_str
                parts = commitment_data.split(":")
                assert len(parts) == 2, f"Commitment data should have 2 parts separated by ':', got {len(parts)} parts"
                commit_sha, content_sha = parts
                assert len(commit_sha) == 40, f"Commit SHA should be 40 characters long, got {len(commit_sha)} characters"
                assert len(content_sha) == 64, f"Content SHA should be 64 characters long, got {len(content_sha)} characters"              
                success += 1
            except Exception as e:
                print(f"Error parsing commitment {i}: {e}")                
                errors += 1
                continue
    print(f"Total successful verifications: {success}")
    print(f"Total errors: {errors}")



def test_get_gist_sha_commits():
    gist_id = GIST_ID
    commits = get_gist_sha_commits(gist_id)
    print(f"Commits for Gist {gist_id}: {commits}")
    assert isinstance(commits, list), "Commits should be a list"
    assert len(commits) > 0, "There should be at least one commit"
    for sha in commits:
        assert isinstance(sha, str), "Each commit SHA should be a string"
        assert len(sha) == 40, "Each commit SHA should be 40 characters long"
    print(f"Total of {len(commits)} commits found for Gist {gist_id}")
    

@pytest.mark.asyncio
async def test_is_commitment_valid():    
    created_at = datetime.now(timezone.utc).isoformat()
    preamble = f"{created_at}:{GITHUB_ACCOUNT}:{GIST_ID}:{MINER_WALLET_HOTKEY}"
    signature = MINER_WALLET.hotkey.sign(preamble).hex()
    miner_submission = MinerSubmission(
        created_at=created_at,
        github_account=GITHUB_ACCOUNT,
        gist_id=GIST_ID,
        hotkey=MINER_WALLET_HOTKEY,
        signature=signature
    )
    
    #commited = await commit_to_chain(GITHUB_ACCOUNT, GIST_ID, MINER_WALLET_NAME, MINER_WALLET_HOTKEY_NAME)
    commited, current_block = await commit_to_chain_with_wallet(miner_submission.github_account, miner_submission.gist_id, MINER_WALLET)
    print(f"Commitment to chain result: {commited}")
    assert commited, "Commitment to chain should succeed for the test submission"
    assert current_block is not None, "Current block number should be returned after commitment"
    
    valid, block = await is_commitment_valid(miner_submission)
    print(f"Is commitment valid? {valid} on block {block}")
    assert valid, "Commitment should be valid for the test submission"
    assert block == current_block, f"Block number from validation should match the block number from commitment, got {block} and {current_block}"

@pytest.mark.asyncio
async def test_commit_block_info():  
    sub = await get_subtensor()
    current_block = await sub.get_current_block()
    print(f"Current block number: {current_block}")
    assert isinstance(current_block, int), "Current block number should be an integer"
