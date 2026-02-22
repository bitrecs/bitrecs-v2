from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field

class Payment(BaseModel):
    payment_block_hash: str
    payment_extrinsic_index: str
    agent_id: UUID
    miner_hotkey: str
    miner_coldkey: str
    amount_rao: int
    created_at: datetime


class UploadPriceResponse(BaseModel):
    """Response model for successful agent upload"""
    amount_rao: int = Field(..., description="Amount to send for evaluation (in RAO)")
    send_address: str = Field(..., description="TAO address to send evaluation payment to")