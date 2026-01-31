import os
import asyncio
import httpx
import logging
import random
from datetime import datetime, timezone
from models.agent import Agent
from rules.agent_validator import validate_artifact_template
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

SERVICE_URL = "http://localhost:8000"
client = httpx.Client(base_url=SERVICE_URL)


def test_get_root():
    response = client.get("/")    
    logger.info("Root endpoint response: %s", response.json())    
    result = response.json()
    assert response.status_code == 200
    assert result["message"] == "Bitrecs V2 Testnet"
    
def test_get_health():
    response = client.get("/health")
    logger.info("Health endpoint response: %s", response.json())
    result = response.json()
    assert response.status_code == 200
    assert result["status"] == "healthy"
    assert result["message"] == "OK"
    assert result["db_status"] == "OK"

def test_get_artifacts():
    limit = 4
    response = client.get(f"/artifacts?limit={limit}")    
    logger.info("Artifacts endpoint response: %s", response.json())    
    result = response.json()
    assert response.status_code == 200
    assert "artifacts" in result
    assert len(result["artifacts"]) == limit

def test_get_single_artifact():    
    list_response = client.get("/artifacts?limit=1")
    list_result = list_response.json()
    assert list_response.status_code == 200
    assert "artifacts" in list_result
    assert len(list_result["artifacts"]) > 0

    artifact_id = list_result["artifacts"][0]["agent_id"]
    
    response = client.get(f"/artifact/{artifact_id}")
    logger.info("Single artifact endpoint response: %s", response.json())
    result = response.json()
    assert response.status_code == 200
    assert "agent_id" in result
    assert result["agent_id"] == artifact_id


def test_submit_artifact_invalid_vars():
    """Test submitting an artifact via POST /artifact."""
    sample_artifact = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "miner_hotkey": "test_hotkey",
        "miner_uid": 123,
        "provider": "test_provider",
        "model": "test_model",
        "system_prompt_template": "System prompt Unit Test",
        "user_prompt_template": "User prompt Unit Test",
        "sampling_params": {"temperature": 0.7},
        "fewshot_examples": [{"role": "user", "content": "Hello"}],
        "eval_scores": {"accuracy": 0.95},
        "version_num": 1,
        "status": "screening_1",
        "name": "Test Artifact Unit Test",
        "ip_address": "127.0.0.1"  
    }
    validated, reason = validate_artifact_template(Agent(**sample_artifact))
    assert validated == False, "Artifact validation should fail due to invalid vars"




def generate_random_sentences(num_sentences=5, words_per_sentence=10):
    """
    Generate a string of random sentences for adding non-determinism to unit tests.
    Uses basic word lists to create varied, fake prompts.
    """
    adjectives = ["quick", "lazy", "bright", "dark", "happy", "sad", "big", "small", "hot", "cold"]
    nouns = ["dog", "cat", "house", "car", "tree", "book", "computer", "phone", "city", "river"]
    verbs = ["runs", "jumps", "eats", "sleeps", "reads", "writes", "drives", "flies", "swims", "dances"]
    adverbs = ["quickly", "slowly", "happily", "sadly", "loudly", "quietly", "carefully", "wildly"]
    
    sentences = []
    for _ in range(num_sentences):
        words = []
        for _ in range(words_per_sentence):
            word_type = random.choice(["adj", "noun", "verb", "adv"])
            if word_type == "adj":
                words.append(random.choice(adjectives))
            elif word_type == "noun":
                words.append(random.choice(nouns))
            elif word_type == "verb":
                words.append(random.choice(verbs))
            else:
                words.append(random.choice(adverbs))
        sentence = " ".join(words).capitalize() + "."
        sentences.append(sentence)
    
    return " ".join(sentences)

def test_submit_artifact_valid_vars_local():
    """Test submitting an artifact to LOCALHOST"""
    
    prompt = generate_random_sentences(3, 12)
    miner_uid = random.randint(1, 255)
        
    system_prompt = "System prompt {{sku}} Unit Test with more characters"
    #user_prompt = "User prompt {{sku}} Unit Test with random text" + prompt
    user_prompt = "User prompt {{sku}} Unit Test with random text"
    
    sample_artifact = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "miner_hotkey": "test_hotkey",
        "miner_uid": miner_uid,
        "provider": "CHUTES",
        "model": "z-ai/glm-4.7-flash",
        "system_prompt_template": system_prompt,
        "user_prompt_template": user_prompt,
        "sampling_params": {"temperature": 1.1},
        "fewshot_examples": [{"role": "user", "content": "Hello"}],
        "eval_scores": {"accuracy": 0.95},
        "version_num": 1,
        "status": "screening_1",
        "name": "Test Artifact Unit Test",
        "ip_address": "127.0.0.1"  
    }

    validated, reason = validate_artifact_template(Agent(**sample_artifact))
    assert True == validated, f"Artifact validation failed: {reason}"
    
    response = client.post("/artifact", json=sample_artifact)
    result = response.json()
    logger.info(f"Submit artifact response: {result}")
    
    assert 201 == response.status_code, f"Expected status 201, got {response.status_code}"
    assert "message" in result
    assert result["message"] == "Artifact submitted successfully"


def test_submit_artifact_valid_vars_pub():
    """Test submitting an artifact to PRODUCTION"""
    
    prompt = generate_random_sentences(6, 16)
    miner_uid = random.randint(1, 255)
        
    system_prompt = "System prompt {{sku}} Unit Test with more characters"    
    #user_prompt = "User prompt {{sku}} Unit Test {{fake_variable}} with random text:" + prompt
    #user_prompt = "User prompt {{sku}} Unit Test with random text:" + prompt
    user_prompt = "User prompt {{sku}} Unit Test"
    
    model = "google/gemini-2.5-flash-lite"
    sample_artifact = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "miner_hotkey": "5HgU7B3xfSfisR1A7wDMt7FHX5Uizj6xtWWHwhwJMZSrdN7y",
        "miner_uid": miner_uid,
        "provider": "OPEN_ROUTER",
        "model": model,
        "system_prompt_template": system_prompt,
        "user_prompt_template": user_prompt,
        "sampling_params": {"temperature": 0.3},
        "fewshot_examples": [{"role": "user", "content": "Hello"}],
        "eval_scores": {"accuracy": 0.95},
        "version_num": 1,
        "status": "screening_1",
        "name": f"Test Artifact Unit Test - {model}",
        "ip_address": "127.0.0.1"  
    }

    validated, reason = validate_artifact_template(Agent(**sample_artifact))
    assert True == validated, f"Artifact validation failed: {reason}"

    #new_url = "http://localhost:8000"
    new_url = os.environ.get("RIDGES_PLATFORM_URL", "")
    print(f"Using RIDGES_PLATFORM_URL: {new_url}")

    client = httpx.Client(base_url=new_url)
    response = client.post("/artifact", json=sample_artifact)
    result = response.json()
    logger.info(f"Submit artifact response: {result}")
    
    assert 201 == response.status_code, f"Expected status 201, got {response.status_code}"
    assert "message" in result
    assert result["message"] == "Artifact submitted successfully"


async def test_dashboard_rate_limit():
    """Test that dashboard endpoint rate limiting works"""
    base_url = SERVICE_URL
    
    async with httpx.AsyncClient() as client:
        # Make 31 requests to /dashboard/ (limit is 30/minute)
        print("Making 31 requests to /dashboard/...")
        responses = []
        
        for i in range(31):
            response = await client.get(f"{base_url}/dashboard/")
            responses.append(response.status_code)
            print(f"Request {i+1}: Status {response.status_code}")
            
            # Small delay to avoid connection issues
            await asyncio.sleep(0.1)
        
        # Count 200s and 429s
        success_count = responses.count(200)
        rate_limited_count = responses.count(429)
        
        print(f"\nResults:")
        print(f"Successful (200): {success_count}")
        print(f"Rate Limited (429): {rate_limited_count}")
        
        # Should have 30 successful and 1 rate limited
        assert success_count == 30, f"Expected 30 successful requests, got {success_count}"
        assert rate_limited_count == 1, f"Expected 1 rate limited request, got {rate_limited_count}"
        print("\n✅ Test passed! Rate limiting is working correctly.")


async def test_health_rate_limit():
    """Test that dashboard endpoint rate limiting works"""
    #base_url = SERVICE_URL
    base_url ="https://v2.testnet.api.bitrecs.ai"
    async with httpx.AsyncClient() as client:
        
        print("Making 61 requests to /health/...")
        responses = []
        
        for i in range(61):
            response = await client.get(f"{base_url}/health")
            responses.append(response.status_code)
            print(f"Request {i+1}: Status {response.status_code}")
            
            # Small delay to avoid connection issues
            await asyncio.sleep(0.1)
        
        # Count 200s and 429s
        success_count = responses.count(200)
        rate_limited_count = responses.count(429)
        
        print(f"\nResults:")
        print(f"Successful (200): {success_count}")
        print(f"Rate Limited (429): {rate_limited_count}")
        
        # Should have 30 successful and 1 rate limited
        assert success_count == 30, f"Expected 30 successful requests, got {success_count}"
        assert rate_limited_count == 1, f"Expected 1 rate limited request, got {rate_limited_count}"
        print("\n✅ Test passed! Rate limiting is working correctly.")