from pydantic import BaseModel, Field, condecimal, ConfigDict
from typing import Literal, Optional
from datetime import datetime

class PaymentRequest(BaseModel):
    booking_id: int
    simulate: Optional[Literal["success", "failed", "pending"]] = None
    
class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    amount: condecimal(max_digits=10, decimal_places=2)
    status: str
    provider_ref: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class WebhookPayload(BaseModel):
    event_id: str = Field(min_length=1)
    provider_ref: str = Field(min_length=1)
    status: Literal["SUCCESS", "FAILED"]
