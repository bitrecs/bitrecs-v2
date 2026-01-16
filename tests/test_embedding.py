import pytest
import httpx
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMBEDDING_SERVER_URL = "http://localhost:8080"

@pytest.fixture(scope="session")
async def embedding_server_available():
    """Fixture to check if the embedding server is available by testing the /embed endpoint. Returns True if available, False otherwise."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.info("Checking embedding server availability at %s", EMBEDDING_SERVER_URL)
            response = await client.post(
                f"{EMBEDDING_SERVER_URL}/embed",
                json={"inputs": ["test"]}
            )
            logger.info("Response status: %d, body: %s", response.status_code, response.text[:200])  # Log first 200 chars of response
            if response.status_code == 200:
                data = response.json()
                # TEI /embed returns a list of embeddings directly, not wrapped in {"embeddings": [...]}
                if isinstance(data, list) and len(data) == 1 and isinstance(data[0], list):
                    logger.info("Embedding server is available.")
                    return True
            logger.warning("Embedding server check failed: status %d, unexpected response format", response.status_code)
            return False
    except httpx.ConnectError as e:
        logger.error("Connection error: %s", str(e))
        return False
    except httpx.TimeoutException as e:
        logger.error("Timeout error: %s", str(e))
        return False
    except httpx.RemoteProtocolError as e:
        logger.error("Remote protocol error: %s", str(e))
        return False
    except Exception as e:
        logger.error("Unexpected error: %s", str(e))
        return False

@pytest.mark.asyncio
async def test_embedding_server_basic(embedding_server_available):
    """
    Unit test to verify the local embedding server is running and returns valid embeddings.
    
    Sends a POST request to /embed with sample text inputs and checks:
    - HTTP status is 200
    - Response is a list of lists (embeddings)
    - Each embedding has the expected dimension (768 for all-mpnet-base-v2)
    """
    assert embedding_server_available, "Embedding server is not available. Check logs for details."
    
    sample_inputs = ["Hello world", "This is a test sentence"]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{EMBEDDING_SERVER_URL}/embed",
            json={"inputs": sample_inputs}
        )
        
        # Assert successful response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Parse JSON response (TEI returns list of embeddings directly)
        embeddings = response.json()
        assert isinstance(embeddings, list), "Response should be a list of embeddings"
        assert len(embeddings) == len(sample_inputs), f"Expected {len(sample_inputs)} embeddings, got {len(embeddings)}"
        
        # Check embedding dimensions (768 for all-mpnet-base-v2)
        expected_dim = 768
        for i, emb in enumerate(embeddings):
            assert isinstance(emb, list), f"Embedding {i} should be a list"
            assert len(emb) == expected_dim, f"Embedding {i} should have {expected_dim} dimensions, got {len(emb)}"
            # Ensure values are floats
            assert all(isinstance(val, float) for val in emb), f"Embedding {i} should contain floats"

@pytest.mark.asyncio
async def test_embedding_server_empty_input(embedding_server_available):
    """
    Test edge case: Empty input list.
    TEI server returns 400 for empty inputs, as it's invalid.
    """
    assert embedding_server_available, "Embedding server is not available. Check logs for details."
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{EMBEDDING_SERVER_URL}/embed",
            json={"inputs": []}
        )
        
        # TEI returns 400 for empty inputs
        assert response.status_code == 400, f"Expected 400 for empty input, got {response.status_code}: {response.text}"
        # Optionally check error message
        data = response.json()
        assert "error" in data or "message" in data, "Error response should contain error details"

@pytest.mark.asyncio
async def test_embedding_server_invalid_request(embedding_server_available):
    """
    Test error handling: Invalid request (missing inputs).
    """
    assert embedding_server_available, "Embedding server is not available. Check logs for details."
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{EMBEDDING_SERVER_URL}/embed",
            json={}  # Missing inputs
        )
        
        # TEI server should return 422 or similar for invalid input
        assert response.status_code in [400, 422], f"Expected 400/422 for invalid request, got {response.status_code}"