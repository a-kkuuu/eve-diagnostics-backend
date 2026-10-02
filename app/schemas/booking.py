from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

class BookingCreate(BaseModel):
    centre_id: int
    test_id: int
    appointment_at: datetime
    
    @field_validator('appointment_at')
    @classmethod
    def validate_timezone_and_future(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("appointment_at must include timezone information")
        if v < datetime.now(timezone.utc):
            raise ValueError("appointment_at must be in the future")
        return v

class BookingOut(BaseModel):
    id: int
    centre_id: int
    test_id: int
    appointment_at: datetime
    amount: Decimal
    status: str
    created_at: datetime
    centre_name: str
    test_name: str
    
    model_config = ConfigDict(from_attributes=True)
