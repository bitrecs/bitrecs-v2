import os
import httpx
import utils.logger as logger
from dataclasses import dataclass


@dataclass
class AgoraStatus:
    id: str
    from_server: str
    priority: int
    description: str
    status: str


async def post_to_agora(payload: AgoraStatus) -> None:   
    try:
        url = os.environ.get("AGORA_URL", "")
        key = os.environ.get("AGORA_API_KEY", "")
        headers = {"Content-Type": "application/json", "X-API-Key": key}
        async with httpx.AsyncClient(base_url=url, headers=headers) as client:
            response = await client.post("/submit", json=payload.__dict__)
            response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to post to Agora: {e}")


async def post_weights_to_agora(hotkey: str, block: int, uids: list[int], weights: list[float], status: str) -> None:    
    try:
        from utils.agora import post_to_agora, AgoraStatus
        weight_info = {f"uid{uid}": weight for uid, weight in zip(uids, weights)}
        payload = AgoraStatus(
            id="validator",
            from_server=hotkey,
            priority=1,
            description=str({"block": block, "weights": weight_info}),
            status=status
        )
        await post_to_agora(payload)
    except Exception as e:
        logger.error(f"post_weights_to_agora failed to post weights to Agora: {e}")