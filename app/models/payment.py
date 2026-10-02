from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Enum, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum
import uuid
from datetime import datetime, timezone
from app.database import Base

class PaymentStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

def generate_provider_ref():
    return "pay_" + uuid.uuid4().hex

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, nullable=False, default=PaymentStatus.PENDING.value)
    provider_ref = Column(String, unique=True, nullable=False, default=generate_provider_ref)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    booking = relationship("Booking", back_populates="payments")
    
    __table_args__ = (
        CheckConstraint(status.in_([s.value for s in PaymentStatus]), name="chk_payment_status"),
        Index("uq_successful_payment_per_booking", booking_id, unique=True, postgresql_where=(status == 'SUCCESS')),
    )

class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, nullable=False)
    provider_ref = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    received_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
