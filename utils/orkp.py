import httpx
import utils.logger as logger
from datetime import datetime, timedelta, timezone
from typing import Optional


OPENROUTER_MGMT_URL = "https://openrouter.ai/api/v1/keys"

DEFAULT_KEY_EXPIRY_HOURS = 2
DEFAULT_KEY_CREDIT_LIMIT_USD = 2.0

async def create_temporary_openrouter_key(
    mgmt_key: str,
    name: str,
    expires_in_hours: int = DEFAULT_KEY_EXPIRY_HOURS,
    credit_limit_usd: float = DEFAULT_KEY_CREDIT_LIMIT_USD
) -> Optional[str]:
    """
    Creates a temporary OpenRouter API key using a Management Key.
    
    Args:
        mgmt_key: The OpenRouter Management API key (sk-or-mg-...).
        name: A descriptive name for the key (e.g., "miner-<id>-eval-<uuid>").
        expires_in_hours: How long until the key expires.
        credit_limit_usd: The maximum spend allowed on this key.
        
    Returns:
        The generated sk-or-v1-... key string, or None if creation failed.
    """
    
    expiry_date = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)    
    expires_at = expiry_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {
        "Authorization": f"Bearer {mgmt_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": name,
        "expires_at": expires_at,
        "limit": credit_limit_usd,
        "limit_reset": None  # Key is one-time use, no reset
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                OPENROUTER_MGMT_URL,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 201:
                data = response.json()
                # The 'key' is only returned once upon creation
                created_key = data.get("key")
                if created_key:
                    logger.info(f"Successfully created temp OR key: {name}")
                    return created_key
                else:
                    logger.error("OR Management API returned 201 but no key was found in response")
            else:
                logger.error(f"Failed to create OR key. Status: {response.status_code}, Response: {response.text}")
                
    except Exception as e:
        logger.error(f"Exception while creating temporary OpenRouter key: {e}")
        
    return None



async def validate_openrouter_key(key: str, model: str) -> bool:
    """
    Tests OpenRouter key and model with absolute minimal token usage.
    """
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bitrecs.ai",
        "X-Title": "bitrecs-test"
    }

    # 1. First, check key validity and remaining credits (0 tokens)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            auth_response = await client.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
            if auth_response.status_code != 200:
                logger.error(f"OpenRouter key is invalid or inactive: {auth_response.text}")
                return False
            
            key_data = auth_response.json().get("data", {})
            if key_data.get("limit") and (key_data.get("usage", 0) >= key_data.get("limit")):
                logger.error("OpenRouter key has reached its spending limit.")
                return False
    except Exception as e:
        logger.warning(f"Metadata check failed, falling back to minimal completion test: {e}")

    # 2. Test model accessibility with exactly 1 token
    data = {
        "model": model,
        "messages": [{"role": "user", "content": "type '1'"}],
        "max_tokens": 1,  # Minimal output usage
        "temperature": 0.0
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return True
    except Exception as e:
        logger.error(f"Model test failed for {model}: {e}")
        return False