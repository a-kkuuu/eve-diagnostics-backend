from sqlalchemy import Column, Integer, Numeric, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class CentreTest(Base):
    __tablename__ = "centre_tests"

    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), index=True, nullable=False)
    test_id = Column(Integer, ForeignKey("tests.id", ondelete="CASCADE"), index=True, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    centre = relationship("Centre", back_populates="tests")
    test = relationship("Test", back_populates="centres")

    __table_args__ = (
        UniqueConstraint('centre_id', 'test_id', name='uq_centre_test'),
        CheckConstraint('price > 0', name='chk_price_positive')
    )
