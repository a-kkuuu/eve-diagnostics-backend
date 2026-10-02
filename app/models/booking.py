from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, String, CheckConstraint, Index
from sqlalchemy.sql import func
from app.database import Base
from enum import Enum
import sqlalchemy as sa

class BookingStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), nullable=False, index=True)
    test_id = Column(Integer, ForeignKey("tests.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_at = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String, default=BookingStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    centre = sa.orm.relationship("Centre")
    test = sa.orm.relationship("Test")
    payments = sa.orm.relationship("Payment", back_populates="booking")

    @property
    def centre_name(self) -> str:
        return self.centre.name if self.centre else ""

    @property
    def test_name(self) -> str:
        return self.test.name if self.test else ""

    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'CONFIRMED', 'FAILED', 'CANCELLED')", name="chk_booking_status"),
        Index("ix_bookings_user_created", "user_id", "created_at"),
        Index(
            "uq_active_booking",
            "user_id", "centre_id", "test_id", "appointment_at",
            unique=True,
            postgresql_where=sa.text("status IN ('PENDING', 'CONFIRMED')")
        )
    )
