import httpx
import logging
from datetime import datetime, timezone
from models.agent import Agent
from rules.agent_validator import validate_artifact_template

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


def test_submit_artifact():
    """Test submitting an artifact via POST /artifact."""
    sample_artifact = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "miner_hotkey": "test_hotkey",
        "miner_uid": 123,
        "provider": "test_provider",
        "model": "test_model",
        "system_prompt_template": "System prompt",
        "user_prompt_template": "User prompt",
        "sampling_params": {"temperature": 0.7},
        "fewshot_examples": [{"role": "user", "content": "Hello"}],
        "eval_scores": {"accuracy": 0.95},
        "version_num": 1,
        "status": "screening_1",
        "name": "Test Artifact",
        "ip_address": "127.0.0.1"  
    }

    validated, reason = validate_artifact_template(Agent(**sample_artifact))
    assert validated == True, f"Artifact validation failed: {reason}"
    
    response = client.post("/artifact", json=sample_artifact)
    logger.info("Submit artifact response: %s", response.json())
    
    assert response.status_code == 201
    result = response.json()
    assert "message" in result
    assert result["message"] == "Artifact submitted successfully"

