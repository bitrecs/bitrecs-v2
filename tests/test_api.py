import httpx
import logging

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
    limit = 2
    response = client.get(f"/artifacts")    
    logger.info("Artifacts endpoint response: %s", response.json())    
    result = response.json()
    assert response.status_code == 200
    assert "artifacts" in result
    assert len(result["artifacts"]) == limit